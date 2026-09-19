#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

#include "../include/espdevlink_secrets.h"

// Compile-time defaults stay in source; private credentials live in the ignored
// include/espdevlink_secrets.h file and are never committed to GitHub.
const char* DEFAULT_WIFI_SSID = ESPDEVLINK_WIFI_SSID;
const char* DEFAULT_WIFI_PASSWORD = ESPDEVLINK_WIFI_PASSWORD;

// Keep existing private config files compatible. Fallback credentials are
// optional until the user adds them to espdevlink_secrets.h.
#ifndef ESPDEVLINK_FALLBACK_WIFI_SSID
#define ESPDEVLINK_FALLBACK_WIFI_SSID ""
#endif
#ifndef ESPDEVLINK_FALLBACK_WIFI_PASSWORD
#define ESPDEVLINK_FALLBACK_WIFI_PASSWORD ""
#endif

const char* FALLBACK_WIFI_SSID = ESPDEVLINK_FALLBACK_WIFI_SSID;
const char* FALLBACK_WIFI_PASSWORD = ESPDEVLINK_FALLBACK_WIFI_PASSWORD;
const char* ACCESS_CODE = ESPDEVLINK_ACCESS_CODE;

// Runtime Wi-Fi credentials entered through the fallback setup page are
// stored separately from the compile-time primary and secondary networks.
Preferences wifiPreferences;
String WIFI_SSID;
String WIFI_PASSWORD;
String activeWiFiSSID;
bool hasSavedWiFiCredentials = false;

// Cross-network rendezvous settings.
const char* KEYVAL_BASE_URL = "https://api.keyval.org";
const char* KEYVAL_KEY = ESPDEVLINK_KEYVAL_KEY;
const char* RENDEZVOUS_DEVICE_ID = "gaming-pc";

const char* MDNS_NAME = "steamlink";
const char* FALLBACK_AP_NAME = "ESPLink-Setup";
const char* FALLBACK_AP_PASSWORD = "esp-link-setup";

constexpr unsigned long WIFI_TIMEOUT_MS = 15000;
constexpr uint8_t BOOT_BUTTON_PIN = 0; // Built-in BOOT button on ESP32 DevKit V1
constexpr unsigned long FALLBACK_HOLD_MS = 3000;
constexpr unsigned long PC_TIMEOUT_MS = 5000;
constexpr size_t MAX_HEARTBEAT_BYTES = 2048;
constexpr size_t MAX_WIFI_SSID_BYTES = 64;
constexpr size_t MAX_WIFI_PASSWORD_BYTES = 64;

AsyncWebServer server(80);
String pcName = "Gaming PC";
String pcIP = "";
String currentGame = "";
String streamState = "Ready";
String pcConnectionMode = "AUTOMATIC";
String wifiMode = "disconnected";
String wifiLastFailure = "";
uint8_t wifiAttempts = 0;
String activeSession = "";
String pcSession = "";
unsigned long lastPCHeartbeat = 0;
bool pcKnown = false;
bool mdnsReady = false;
String remoteURL = "";
bool remoteOnline = false;
unsigned long remoteCheckedAt = 0;
constexpr unsigned long REMOTE_LOOKUP_INTERVAL_MS = 30000;

bool pcOnline() { return pcKnown && millis() - lastPCHeartbeat <= PC_TIMEOUT_MS; }

void loadWiFiCredentials() {
    wifiPreferences.begin("wifi", false);
    hasSavedWiFiCredentials = wifiPreferences.isKey("ssid");
    if (hasSavedWiFiCredentials) {
        WIFI_SSID = wifiPreferences.getString("ssid", "");
        WIFI_PASSWORD = wifiPreferences.getString("password", "");
    } else {
        WIFI_SSID = "";
        WIFI_PASSWORD = "";
    }
    activeWiFiSSID = "";
    Serial.print("Saved Wi-Fi SSID: ");
    Serial.println(hasSavedWiFiCredentials && WIFI_SSID.length() ? WIFI_SSID : "(none)");
}

void saveWiFiCredentials(const String& ssid, const String& password) {
    wifiPreferences.putString("ssid", ssid);
    wifiPreferences.putString("password", password);
    WIFI_SSID = ssid;
    WIFI_PASSWORD = password;
    activeWiFiSSID = ssid;
    hasSavedWiFiCredentials = true;
}

bool lookupRemoteURL() {
    if (strlen(KEYVAL_KEY) < 10 || strlen(RENDEZVOUS_DEVICE_ID) == 0) {
        remoteURL = "";
        remoteOnline = false;
        return false;
    }
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    String endpoint = String(KEYVAL_BASE_URL) + "/get";
    if (!http.begin(client, endpoint)) {
        remoteOnline = false;
        return false;
    }
    http.setTimeout(5000);
    http.addHeader("Content-Type", "application/json");
    String requestBody = String("{\"key\":\"") + KEYVAL_KEY + "\"}";
    int code = http.POST(requestBody);
    if (code != HTTP_CODE_OK) {
        http.end();
        remoteOnline = false;
        return false;
    }
    String payload = http.getString();
    http.end();
    payload.trim();

    // KeyVal's POST /get API returns JSON, e.g.
    // {"status":"SUCCESS","key":"...","val":"https://....trycloudflare.com"}
    JsonDocument responseDoc;
    DeserializationError parseError = deserializeJson(responseDoc, payload);
    if (parseError) {
        remoteOnline = false;
        remoteURL = "";
        return false;
    }

    const char* value = responseDoc["val"] | "";
    if (strlen(value) == 0 || strncmp(value, "https://", 8) != 0 ||
        strstr(value, ".trycloudflare.com") == nullptr) {
        remoteOnline = false;
        remoteURL = "";
        return false;
    }

    remoteURL = value;
    remoteOnline = true;
    return true;
}

void sendJson(AsyncWebServerRequest* request, JsonDocument& doc, int code = 200) {
    String output;
    serializeJson(doc, output);
    request->send(code, "application/json", output);
}

void sendError(AsyncWebServerRequest* request, int code, const char* message) {
    JsonDocument doc;
    doc["ok"] = false;
    doc["error"] = message;
    sendJson(request, doc, code);
}

bool configuredWiFi() {
    return strlen(DEFAULT_WIFI_SSID) > 0 && strcmp(DEFAULT_WIFI_SSID, "YOUR_WIFI_NAME") != 0;
}

bool configuredSavedWiFi() {
    return hasSavedWiFiCredentials &&
           WIFI_SSID.length() > 0 &&
           WIFI_SSID != "YOUR_WIFI_NAME";
}

bool configuredFallbackWiFi() {
    return strlen(FALLBACK_WIFI_SSID) > 0 &&
           strcmp(FALLBACK_WIFI_SSID, "YOUR_FALLBACK_WIFI_NAME") != 0;
}

String wifiFailureReason() {
    switch (WiFi.status()) {
        case WL_NO_SSID_AVAIL: return "SSID not found";
        case WL_CONNECT_FAILED: return "Connection failed (check password/security)";
        case WL_CONNECTION_LOST: return "Connection lost";
        case WL_DISCONNECTED: return "Disconnected / no association";
        default: return "Wi-Fi connection timed out";
    }
}

bool tryWiFiNetwork(const char* ssid, const char* password, const char* label) {
    if (ssid == nullptr || strlen(ssid) == 0) return false;

    WiFi.disconnect(true, true);
    delay(100);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    wifiAttempts++;

    Serial.print("Connecting to ");
    Serial.print(label);
    Serial.print(" Wi-Fi (SSID: ");
    Serial.print(ssid);
    Serial.print(")");

    const unsigned long startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < WIFI_TIMEOUT_MS) {
        delay(250);
        Serial.print('.');
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        activeWiFiSSID = ssid;
        wifiMode = "station";
        Serial.print("Wi-Fi connected using ");
        Serial.print(label);
        Serial.print(" network. IP: ");
        Serial.println(WiFi.localIP());
        return true;
    }

    wifiLastFailure = wifiFailureReason();
    Serial.print(label);
    Serial.print(" Wi-Fi failure reason: ");
    Serial.println(wifiLastFailure);
    return false;
}

void startFallbackAP() {
    WiFi.mode(WIFI_AP_STA);
    bool started = WiFi.softAP(FALLBACK_AP_NAME, FALLBACK_AP_PASSWORD);
    wifiMode = started ? "fallback_ap" : "disconnected";
    Serial.print("Fallback AP: ");
    Serial.println(started ? "started" : "failed");
    if (started) {
        Serial.print("AP address: http://");
        Serial.println(WiFi.softAPIP());
        Serial.print("AP password: ");
        Serial.println(FALLBACK_AP_PASSWORD);
    }
}

bool fallbackButtonHeld() {
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);
    if (digitalRead(BOOT_BUTTON_PIN) != LOW) return false;
    Serial.println("BOOT button held; checking for forced fallback...");
    const unsigned long startedAt = millis();
    while (digitalRead(BOOT_BUTTON_PIN) == LOW && millis() - startedAt < FALLBACK_HOLD_MS) delay(25);
    if (millis() - startedAt >= FALLBACK_HOLD_MS) {
        Serial.println("Forced fallback requested.");
        return true;
    }
    return false;
}

void connectWiFi(bool forceFallback = false) {
    if (forceFallback) {
        startFallbackAP();
        return;
    }

    // Credentials entered on the fallback setup page are tried first, but
    // never replace the compile-time primary or secondary configuration.
    if (configuredSavedWiFi()) {
        Serial.println("Trying saved Wi-Fi credentials first...");
        if (tryWiFiNetwork(WIFI_SSID.c_str(), WIFI_PASSWORD.c_str(), "saved")) {
            wifiLastFailure = "";
            return;
        }
    }

    if (configuredWiFi()) {
        Serial.println("Trying primary Wi-Fi network...");
        if (tryWiFiNetwork(DEFAULT_WIFI_SSID, DEFAULT_WIFI_PASSWORD, "primary")) {
            wifiLastFailure = "";
            return;
        }
    } else {
        Serial.println("Primary Wi-Fi credentials are not configured.");
    }

    if (configuredFallbackWiFi()) {
        Serial.println("Primary Wi-Fi unavailable; trying secondary network...");
        if (tryWiFiNetwork(FALLBACK_WIFI_SSID, FALLBACK_WIFI_PASSWORD, "secondary")) {
            wifiLastFailure = "Primary network unavailable; connected to secondary network";
            return;
        }
    } else {
        Serial.println("No secondary Wi-Fi network is configured.");
    }

    wifiLastFailure = "Saved, primary, and secondary Wi-Fi networks unavailable";
    Serial.println("No configured Wi-Fi network could be reached.");
    startFallbackAP();
}

void startMDNS() {
    mdnsReady = MDNS.begin(MDNS_NAME);
    if (mdnsReady) {
        MDNS.addService("http", "tcp", 80);
        Serial.print("mDNS available at: http://");
        Serial.print(MDNS_NAME);
        Serial.println(".local");
    } else {
        Serial.println("mDNS failed; use the printed IP address.");
    }
}

bool authorized(AsyncWebServerRequest* request) {
    if (activeSession.length() == 0) return false;
    return request->hasHeader("X-ESPLink-Session") &&
           request->getHeader("X-ESPLink-Session")->value() == activeSession;
}

bool pcAuthorized(AsyncWebServerRequest* request) {
    if (pcSession.length() == 0) return false;
    return request->hasHeader("X-ESPLink-PC-Session") &&
           request->getHeader("X-ESPLink-PC-Session")->value() == pcSession;
}

void handleHeartbeatBody(AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
    static String body;
    if (!pcAuthorized(request)) {
        if (index + len == total) sendError(request, 401, "Unauthorized");
        return;
    }
    if (index == 0) {
        body = "";
        if (total > MAX_HEARTBEAT_BYTES) {
            sendError(request, 413, "Heartbeat body is too large");
            return;
        }
        body.reserve(total);
    }
    if (body.length() + len > MAX_HEARTBEAT_BYTES) {
        body = "";
        sendError(request, 413, "Heartbeat body is too large");
        return;
    }
    for (size_t i = 0; i < len; ++i) body += static_cast<char>(data[i]);
    if (index + len != total) return;
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, body);
    if (error || !doc.is<JsonObject>()) {
        body = "";
        sendError(request, 400, "Invalid JSON heartbeat");
        return;
    }
    if (doc["name"].is<const char*>()) pcName = doc["name"].as<String>();
    if (doc["ip"].is<const char*>()) pcIP = doc["ip"].as<String>();
    if (doc["game"].is<const char*>()) currentGame = doc["game"].as<String>();
    if (doc["stream"].is<const char*>()) streamState = doc["stream"].as<String>();
    if (doc["connection_mode"].is<const char*>()) pcConnectionMode = doc["connection_mode"].as<String>();
    pcKnown = true;
    lastPCHeartbeat = millis();
    JsonDocument response;
    response["ok"] = true;
    response["online"] = true;
    sendJson(request, response);
    body = "";
}

void setup() {
    Serial.begin(115200);
    delay(250);
    Serial.println();
    Serial.println("==============================");
    Serial.println("       ESPLink Starting");
    Serial.println("==============================");
    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS mount failed!");
        return;
    }
    Serial.println("LittleFS mounted.");
    loadWiFiCredentials();
    const bool forceFallback = fallbackButtonHeld();
    connectWiFi(forceFallback);
    startMDNS();

    server.serveStatic("/", LittleFS, "/")
        .setDefaultFile("index.html")
        .setCacheControl("no-cache");

    server.on("/api/auth/login", HTTP_POST, [](AsyncWebServerRequest* request) {}, nullptr,
        [](AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
            static String body;
            if (index == 0) body = "";
            if (body.length() + len > 1024) {
                body = "";
                sendError(request, 413, "Login body is too large");
                return;
            }
            for (size_t i = 0; i < len; ++i) body += static_cast<char>(data[i]);
            if (index + len != total) return;
            JsonDocument input;
            if (deserializeJson(input, body) || !input["code"].is<const char*>()) {
                body = "";
                sendError(request, 400, "Invalid login request");
                return;
            }
            if (input["code"].as<String>() != ACCESS_CODE) {
                body = "";
                sendError(request, 401, "Invalid authorization code");
                return;
            }
            activeSession = String((uint32_t)esp_random(), HEX) + String((uint32_t)esp_random(), HEX);
            JsonDocument output;
            output["ok"] = true;
            output["session_id"] = activeSession;
            output["session_type"] = "browser";
            sendJson(request, output);
            body = "";
        });

    server.on("/api/pc/login", HTTP_POST, [](AsyncWebServerRequest* request) {}, nullptr,
        [](AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
            static String body;
            if (index == 0) body = "";
            if (body.length() + len > 1024) {
                body = "";
                sendError(request, 413, "Login body is too large");
                return;
            }
            for (size_t i = 0; i < len; ++i) body += static_cast<char>(data[i]);
            if (index + len != total) return;
            JsonDocument input;
            if (deserializeJson(input, body) || !input["code"].is<const char*>()) {
                body = "";
                sendError(request, 400, "Invalid login request");
                return;
            }
            if (input["code"].as<String>() != ACCESS_CODE) {
                body = "";
                sendError(request, 401, "Invalid authorization code");
                return;
            }
            pcSession = String((uint32_t)esp_random(), HEX) + String((uint32_t)esp_random(), HEX);
            JsonDocument output;
            output["ok"] = true;
            output["session_id"] = pcSession;
            output["session_type"] = "pc";
            sendJson(request, output);
            body = "";
        });

    // Wi-Fi provisioning is intentionally available only while the ESP32 is
    // running its protected fallback setup AP. Saving credentials restarts the
    // ESP32 so it immediately attempts the new network.
    server.on("/api/wifi/configure", HTTP_POST, [](AsyncWebServerRequest* request) {}, nullptr,
        [](AsyncWebServerRequest* request, uint8_t* data, size_t len, size_t index, size_t total) {
            static String body;
            if (wifiMode != "fallback_ap") {
                if (index + len == total) sendError(request, 409, "Wi-Fi setup is only available in fallback mode");
                return;
            }
            if (index == 0) body = "";
            if (total > 2048 || body.length() + len > 2048) {
                body = "";
                sendError(request, 413, "Wi-Fi configuration is too large");
                return;
            }
            for (size_t i = 0; i < len; ++i) body += static_cast<char>(data[i]);
            if (index + len != total) return;

            JsonDocument input;
            if (deserializeJson(input, body) || !input["ssid"].is<const char*>() || !input["password"].is<const char*>()) {
                body = "";
                sendError(request, 400, "SSID and password are required");
                return;
            }
            String ssid = input["ssid"].as<String>();
            String password = input["password"].as<String>();
            ssid.trim();
            if (ssid.length() == 0 || ssid.length() > MAX_WIFI_SSID_BYTES) {
                body = "";
                sendError(request, 400, "SSID must be 1-64 characters");
                return;
            }
            if (password.length() > MAX_WIFI_PASSWORD_BYTES) {
                body = "";
                sendError(request, 400, "Password must be 64 characters or fewer");
                return;
            }

            saveWiFiCredentials(ssid, password);
            wifiLastFailure = "";
            JsonDocument output;
            output["ok"] = true;
            output["ssid"] = WIFI_SSID;
            output["message"] = "Wi-Fi credentials saved. Restarting...";
            sendJson(request, output);
            body = "";
            delay(750);
            ESP.restart();
        });

    server.on("/api/remote", HTTP_GET, [](AsyncWebServerRequest* request) {
        if (millis() - remoteCheckedAt >= REMOTE_LOOKUP_INTERVAL_MS) {
            lookupRemoteURL();
            remoteCheckedAt = millis();
        }
        JsonDocument doc;
        doc["ok"] = true;
        doc["online"] = remoteOnline;
        doc["url"] = remoteURL;
        doc["device_id"] = RENDEZVOUS_DEVICE_ID;
        sendJson(request, doc);
    });

    // Force an immediate rendezvous refresh after a remote connection failure.
    server.on("/api/remote/refresh", HTTP_POST, [](AsyncWebServerRequest* request) {
        if (!authorized(request)) { sendError(request, 401, "Unauthorized"); return; }
        bool found = lookupRemoteURL();
        remoteCheckedAt = millis();
        JsonDocument doc;
        doc["ok"] = true;
        doc["online"] = found;
        doc["url"] = remoteURL;
        doc["device_id"] = RENDEZVOUS_DEVICE_ID;
        sendJson(request, doc);
    });

    server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* request) {
        JsonDocument doc;
        doc["status"] = "online";
        doc["ip"] = WiFi.localIP().toString();
        doc["ap_ip"] = WiFi.softAPIP().toString();
        doc["mdns"] = String(MDNS_NAME) + ".local";
        doc["mdns_ready"] = mdnsReady;
        doc["wifi_mode"] = wifiMode;
        doc["wifi_rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
        doc["wifi_ssid"] = activeWiFiSSID;
        doc["wifi_status"] = (int)WiFi.status();
        doc["wifi_failure"] = wifiLastFailure;
        doc["wifi_attempts"] = wifiAttempts;
        doc["fallback_ip"] = WiFi.softAPIP().toString();
        doc["pc_online"] = pcOnline();
        doc["remote_online"] = remoteOnline;
        doc["remote_url"] = remoteURL;
        sendJson(request, doc);
    });

    server.on("/api/pc", HTTP_GET, [](AsyncWebServerRequest* request) {
        JsonDocument doc;
        doc["name"] = pcName;
        doc["ip"] = pcIP;
        doc["online"] = pcOnline();
        doc["game"] = currentGame;
        doc["stream"] = streamState;
        doc["connection_mode"] = pcConnectionMode;
        sendJson(request, doc);
    });

    server.on("/api/pc/heartbeat", HTTP_POST, [](AsyncWebServerRequest* request) {}, nullptr, handleHeartbeatBody);

    server.on("/api/connect", HTTP_POST, [](AsyncWebServerRequest* request) {
        if (!authorized(request)) { sendError(request, 401, "Unauthorized"); return; }
        if (!pcOnline()) { sendError(request, 503, "PC is offline"); return; }
        streamState = "Connecting";
        JsonDocument doc;
        doc["ok"] = true;
        doc["pc"] = pcName;
        doc["ip"] = pcIP;
        doc["state"] = streamState;
        sendJson(request, doc);
    });

    server.on("/api/disconnect", HTTP_POST, [](AsyncWebServerRequest* request) {
        if (!authorized(request)) { sendError(request, 401, "Unauthorized"); return; }
        streamState = "Ready";
        JsonDocument doc;
        doc["ok"] = true;
        doc["state"] = streamState;
        sendJson(request, doc);
    });

    server.onNotFound([](AsyncWebServerRequest* request) { request->send(404, "text/plain", "404 Not Found"); });
    server.begin();
    Serial.println("Web server started.");
    Serial.println("ESPLink is ready.");
}

void loop() {
    if (WiFi.status() == WL_CONNECTED && wifiMode != "station") wifiMode = "station";
    if (WiFi.status() == WL_CONNECTED && strlen(KEYVAL_KEY) >= 10 && millis() - remoteCheckedAt >= REMOTE_LOOKUP_INTERVAL_MS) {
        lookupRemoteURL();
        remoteCheckedAt = millis();
    }
}
