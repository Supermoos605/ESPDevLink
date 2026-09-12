#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <LittleFS.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// Replace these placeholders only in your local working copy before building.
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* ACCESS_CODE = "YOUR_ACCESS_CODE";

// Cross-network rendezvous settings. Leave RENDEZVOUS_URL empty to disable remote lookup.
const char* KEYVAL_BASE_URL = "https://api.keyval.org";
// TODO: move this to persistent configuration before release.
const char* KEYVAL_KEY = "CHANGE_ME_TO_A_LONG_RANDOM_KEY";
const char* RENDEZVOUS_DEVICE_ID = "gaming-pc";

const char* MDNS_NAME = "steamlink";
const char* FALLBACK_AP_NAME = "ESPLink-Setup";
const char* FALLBACK_AP_PASSWORD = "esp-link-setup";

constexpr unsigned long WIFI_TIMEOUT_MS = 15000;
constexpr unsigned long PC_TIMEOUT_MS = 5000;
constexpr size_t MAX_HEARTBEAT_BYTES = 2048;

AsyncWebServer server(80);
String pcName = "Gaming PC";
String pcIP = "";
String signalingURL = "";
String currentGame = "";
String streamState = "Ready";
String wifiMode = "disconnected";
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

bool lookupRemoteURL() {
    if (strlen(KEYVAL_KEY) < 10 || strlen(RENDEZVOUS_DEVICE_ID) == 0) {
        remoteURL = "";
        remoteOnline = false;
        return false;
    }
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    String endpoint = String(KEYVAL_BASE_URL) + "/get/" + KEYVAL_KEY;
    if (!http.begin(client, endpoint)) {
        remoteOnline = false;
        return false;
    }
    http.setTimeout(5000);
    int code = http.GET();
    if (code != HTTP_CODE_OK) {
        http.end();
        remoteOnline = false;
        return false;
    }
    String payload = http.getString();
    http.end();
    payload.trim();
    if (!payload.startsWith("https://") || payload.indexOf(".trycloudflare.com") < 0) {
        remoteOnline = false;
        remoteURL = "";
        return false;
    }
    remoteURL = payload;
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
    return strlen(WIFI_SSID) > 0 && strcmp(WIFI_SSID, "YOUR_WIFI_NAME") != 0;
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

void connectWiFi() {
    if (!configuredWiFi()) {
        Serial.println("Wi-Fi credentials are not configured.");
        startFallbackAP();
        return;
    }
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("Connecting to Wi-Fi");
    const unsigned long startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < WIFI_TIMEOUT_MS) {
        delay(250);
        Serial.print('.');
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
        wifiMode = "station";
        Serial.print("Wi-Fi connected. IP: ");
        Serial.println(WiFi.localIP());
        return;
    }
    Serial.println("Wi-Fi connection timed out.");
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
    if (doc["signaling_url"].is<const char*>()) signalingURL = doc["signaling_url"].as<String>();
    if (doc["game"].is<const char*>()) currentGame = doc["game"].as<String>();
    if (doc["stream"].is<const char*>()) streamState = doc["stream"].as<String>();
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
    connectWiFi();
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

    server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* request) {
        JsonDocument doc;
        doc["status"] = "online";
        doc["ip"] = WiFi.localIP().toString();
        doc["ap_ip"] = WiFi.softAPIP().toString();
        doc["mdns"] = String(MDNS_NAME) + ".local";
        doc["mdns_ready"] = mdnsReady;
        doc["wifi_mode"] = wifiMode;
        doc["wifi_rssi"] = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
        doc["pc_online"] = pcOnline();
        doc["remote_online"] = remoteOnline;
        doc["remote_url"] = remoteURL;
        sendJson(request, doc);
    });

    server.on("/api/pc", HTTP_GET, [](AsyncWebServerRequest* request) {
        JsonDocument doc;
        doc["name"] = pcName;
        doc["ip"] = pcIP;
        doc["signaling_url"] = signalingURL;
        doc["online"] = pcOnline();
        doc["game"] = currentGame;
        doc["stream"] = streamState;
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
