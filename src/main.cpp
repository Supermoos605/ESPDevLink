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
String activeWiFiPassword;
bool hasSavedWiFiCredentials = false;

// Cross-network rendezvous settings.
const char* KEYVAL_BASE_URL = "https://api.keyval.org";
const char* KEYVAL_KEY = ESPDEVLINK_KEYVAL_KEY;
const char* RENDEZVOUS_DEVICE_ID = "gaming-pc";

const char* MDNS_NAME = "steamlink";
const char* FALLBACK_AP_NAME = "ESPDev-Recovery";
const char* FALLBACK_AP_PASSWORD = "esp-link-setup";

// ESPDevLink client network. Configure the SSID/password in the private
// include/espdevlink_secrets.h file so the real client network is not hard-coded.
#ifndef ESPDEVLINK_AP_SSID
#define ESPDEVLINK_AP_SSID "ESPDevLink"
#endif
#ifndef ESPDEVLINK_AP_PASSWORD
#define ESPDEVLINK_AP_PASSWORD "espdevlink"
#endif
const char* NAT_AP_NAME = ESPDEVLINK_AP_SSID;
const char* NAT_AP_PASSWORD = ESPDEVLINK_AP_PASSWORD;

const IPAddress NAT_AP_IP(192, 168, 4, 1);
const IPAddress NAT_AP_SUBNET(255, 255, 255, 0);
const IPAddress NAT_AP_LEASE_START(192, 168, 4, 2);

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
bool natAPStarted = false;
bool natEnabled = false;
bool natReconnectPending = false;
unsigned long natReconnectStartedAt = 0;
unsigned long lastNatReconnectAttempt = 0;
unsigned long lastNatAPCheck = 0;
constexpr unsigned long NAT_RECONNECT_INTERVAL_MS = 5000;
constexpr unsigned long NAT_AP_CHECK_INTERVAL_MS = 5000;
String activeSession = "";
String pcSession = "";
unsigned long lastPCHeartbeat = 0;
bool pcKnown = false;
bool mdnsReady = false;
String remoteURL = "";
bool remoteOnline = false;
unsigned long remoteCheckedAt = 0;
constexpr unsigned long REMOTE_LOOKUP_INTERVAL_MS = 5000;

bool pcOnline() { return (pcKnown && millis() - lastPCHeartbeat <= PC_TIMEOUT_MS) || remoteOnline; }

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

// Start the ESPDevLink AP alongside the already-connected STA interface and
// enable ESP32 NAPT so AP clients can use the STA network as their uplink.
// Arduino-ESP32 3.x exposes the AP NetworkInterface, which also lets us
// provide the upstream DNS server to AP clients through DHCP.
bool startNATAP() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("NAT AP not started: STA is not connected.");
        return false;
    }

    WiFi.mode(WIFI_AP_STA);
    delay(100);

    // The ESP32 has one 2.4 GHz radio, so keep the SoftAP on the STA's
    // currently selected channel.
    const uint8_t apChannel = WiFi.channel();

    // Advertise the ESP32 itself as DNS so local names such as "steamlink"
    // can resolve to the ESPDevLink gateway. The DNS proxy forwards all
    // other names to the upstream resolver.
    IPAddress upstreamDNS = WiFi.dnsIP(0);
    if (upstreamDNS == IPAddress(0, 0, 0, 0)) {
        upstreamDNS = IPAddress(1, 1, 1, 1);
    }

    if (!WiFi.AP.config(
            NAT_AP_IP,
            NAT_AP_IP,
            NAT_AP_SUBNET,
            NAT_AP_LEASE_START,
            NAT_AP_IP)) {
        Serial.println("NAT AP IP/DHCP/DNS configuration failed.");
        return false;
    }

    if (!WiFi.softAP(NAT_AP_NAME, NAT_AP_PASSWORD, apChannel, 0, 4)) {
        Serial.println("NAT AP startup failed.");
        return false;
    }

    natAPStarted = true;
    Serial.println();
    Serial.println("ESPDevLink client AP started.");
    Serial.print("  SSID: ");
    Serial.println(NAT_AP_NAME);
    Serial.print("  Password: ");
    Serial.println(NAT_AP_PASSWORD);
    Serial.print("  AP address: http://");
    Serial.println(WiFi.softAPIP());
    Serial.print("  AP channel: ");
    Serial.println(apChannel);
    Serial.print("  Upstream STA address: ");
    Serial.println(WiFi.localIP());
    Serial.print("  AP DHCP DNS: ");
    Serial.println(NAT_AP_IP);
    Serial.print("  Upstream DNS: ");
    Serial.println(upstreamDNS);

    if (!WiFi.AP.enableNAPT(true)) {
        Serial.println("NAPT enable failed.");
        natEnabled = false;
        wifiMode = "station_ap";
        return false;
    }

    natEnabled = true;
    wifiMode = "station_ap_nat";
    Serial.println("NAPT enabled: AP clients now have the STA as their Internet uplink.");
    return true;
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
        activeWiFiPassword = password;
        natReconnectPending = false;
        wifiMode = "station";
        Serial.print("Wi-Fi connected using ");
        Serial.print(label);
        Serial.print(" network. IP: ");
        Serial.println(WiFi.localIP());

        startNATAP();
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
        doc["nat_ap_enabled"] = natAPStarted;
        doc["nat_enabled"] = natEnabled;
        doc["nat_ap_ssid"] = NAT_AP_NAME;
        doc["nat_ap_clients"] = WiFi.softAPgetStationNum();
        doc["nat_ap_ip"] = WiFi.softAPIP().toString();
        doc["pc_online"] = pcOnline();
        doc["pc_name"] = pcName;
        doc["pc_ip"] = pcIP;
        doc["pc_game"] = currentGame;
        doc["pc_stream"] = streamState;
        doc["pc_connection_mode"] = pcConnectionMode;
        doc["remote_online"] = remoteOnline;
        doc["remote_url"] = remoteURL;
        String output;
        serializeJson(doc, output);
        AsyncWebServerResponse* response = request->beginResponse(200, "application/json", output);
        response->addHeader("Access-Control-Allow-Origin", "*");
        response->addHeader("Cache-Control", "no-store");
        request->send(response);
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
    if (natAPStarted && WiFi.status() != WL_CONNECTED) {
        if (natEnabled) {
            WiFi.AP.enableNAPT(false);
            natEnabled = false;
            wifiMode = "station_ap_no_uplink";
            Serial.println("STA uplink lost; NAPT disabled.");
        }
        natReconnectPending = true;
    }

    if (natAPStarted && natReconnectPending && activeWiFiSSID.length() > 0 &&
        millis() - lastNatReconnectAttempt >= NAT_RECONNECT_INTERVAL_MS) {
        lastNatReconnectAttempt = millis();
        Serial.print("NAT uplink reconnect: trying ");
        Serial.println(activeWiFiSSID);
        WiFi.begin(activeWiFiSSID.c_str(), activeWiFiPassword.c_str());
        natReconnectStartedAt = millis();
        natReconnectPending = false;
    }

    if (natAPStarted && WiFi.status() == WL_CONNECTED && !natEnabled) {
        if (WiFi.AP.enableNAPT(true)) {
            natEnabled = true;
            wifiMode = "station_ap_nat";
            wifiLastFailure = "";
            natReconnectStartedAt = 0;
            Serial.println("NAT uplink restored; NAPT re-enabled.");
        }
    }

    if (natAPStarted && WiFi.status() != WL_CONNECTED &&
        natReconnectStartedAt != 0 && millis() - natReconnectStartedAt >= WIFI_TIMEOUT_MS) {
        natReconnectStartedAt = 0;
        natReconnectPending = true;
        wifiLastFailure = wifiFailureReason();
        Serial.print("NAT uplink reconnect timed out: ");
        Serial.println(wifiLastFailure);
    }

    // Keep the SoftAP alive if the AP interface is unexpectedly stopped.
    // This is checked separately from the STA reconnect path so the iPad can
    // remain associated with the ESPDevLink network during upstream recovery.
    if (WiFi.status() == WL_CONNECTED && millis() - lastNatAPCheck >= NAT_AP_CHECK_INTERVAL_MS) {
        lastNatAPCheck = millis();
        const bool apIsUp = natAPStarted && WiFi.softAPIP() == NAT_AP_IP;
        if (!apIsUp) {
            Serial.println("NAT AP is not running; restarting AP/NAPT.");
            natAPStarted = false;
            natEnabled = false;
            startNATAP();
        } else if (!natEnabled) {
            natEnabled = WiFi.AP.enableNAPT(true);
            if (natEnabled) {
                wifiMode = "station_ap_nat";
                Serial.println("NAPT restored while NAT AP remained active.");
            }
        }
    }

    if (WiFi.status() == WL_CONNECTED && strlen(KEYVAL_KEY) >= 10 && (remoteCheckedAt == 0 || millis() - remoteCheckedAt >= REMOTE_LOOKUP_INTERVAL_MS)) {
        lookupRemoteURL();
        remoteCheckedAt = millis();
    }
}
