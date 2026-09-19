#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "espdevlink_secrets.example.h"

namespace {

constexpr uint16_t DNS_PORT = 53;
constexpr uint16_t DNS_MAX_PACKET = 512;
constexpr uint8_t MAX_PENDING = 8;
constexpr uint32_t PENDING_TIMEOUT_MS = 3000;
constexpr uint32_t START_RETRY_MS = 1000;

WiFiUDP dnsUDP;
IPAddress upstreamDNS;
bool dnsStarted = false;

struct PendingQuery {
    bool used = false;
    uint16_t id = 0;
    IPAddress clientIP;
    uint16_t clientPort = 0;
    uint32_t startedAt = 0;
};

PendingQuery pending[MAX_PENDING];

String readQName(const uint8_t* packet, size_t length, size_t& offset) {
    String name;
    if (length < 12 || offset >= length) return name;

    while (offset < length) {
        uint8_t labelLength = packet[offset++];
        if (labelLength == 0) break;

        // Compression pointers are not expected in the question section.
        if ((labelLength & 0xC0) != 0 || offset + labelLength > length) {
            return String();
        }

        if (name.length()) name += '.';
        for (uint8_t i = 0; i < labelLength; ++i) {
            name += static_cast<char>(packet[offset++]);
        }

        if (name.length() > 253) return String();
    }

    name.toLowerCase();
    return name;
}

void expirePending() {
    const uint32_t now = millis();
    for (auto& query : pending) {
        if (query.used && now - query.startedAt > PENDING_TIMEOUT_MS) {
            query.used = false;
        }
    }
}

void answerLocal(const uint8_t* query, size_t length, const IPAddress& clientIP, uint16_t clientPort, bool anyName = false) {
    if (length < 12 || length > DNS_MAX_PACKET) return;

    size_t offset = 12;
    String name = readQName(query, length, offset);
    if ((!anyName && name.length() == 0) || offset + 4 > length || length + 16 > DNS_MAX_PACKET) {
        return;
    }

    uint8_t response[DNS_MAX_PACKET];
    memcpy(response, query, length);

    // QR=1, AA=1, RA=1; preserve the client's opcode and RD bit.
    uint16_t flags = (static_cast<uint16_t>(response[2]) << 8) | response[3];
    flags |= 0x8000; // response
    flags |= 0x0400; // authoritative answer
    flags |= 0x0080; // recursion available
    response[2] = static_cast<uint8_t>(flags >> 8);
    response[3] = static_cast<uint8_t>(flags & 0xFF);

    // One answer, no authority/additional records.
    response[6] = 0;
    response[7] = 1;
    response[8] = response[9] = response[10] = response[11] = 0;

    // Keep the original question section and append an A record.
    size_t out = length;
    response[out++] = 0xC0;
    response[out++] = 0x0C; // pointer to QNAME
    response[out++] = 0x00;
    response[out++] = 0x01; // A
    response[out++] = 0x00;
    response[out++] = 0x01; // IN
    response[out++] = 0x00;
    response[out++] = 0x00;
    response[out++] = 0x00;
    response[out++] = 0x1E; // 30 second TTL
    response[out++] = 0x00;
    response[out++] = 0x04; // IPv4 length

    IPAddress ip(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4);
    for (uint8_t i = 0; i < 4; ++i) {
        response[out++] = ip[i];
    }

    dnsUDP.beginPacket(clientIP, clientPort);
    dnsUDP.write(response, out);
    dnsUDP.endPacket();
}

void rememberForwardedQuery(uint16_t id, const IPAddress& clientIP, uint16_t clientPort) {
    int slot = -1;
    uint32_t oldest = UINT32_MAX;

    for (uint8_t i = 0; i < MAX_PENDING; ++i) {
        if (!pending[i].used) {
            slot = i;
            break;
        }
        if (pending[i].startedAt < oldest) {
            oldest = pending[i].startedAt;
            slot = i;
        }
    }

    pending[slot].used = true;
    pending[slot].id = id;
    pending[slot].clientIP = clientIP;
    pending[slot].clientPort = clientPort;
    pending[slot].startedAt = millis();
}

bool forwardResponse(const uint8_t* packet, size_t length) {
    if (length < 12) return false;

    uint16_t id = (static_cast<uint16_t>(packet[0]) << 8) | packet[1];

    for (auto& query : pending) {
        if (!query.used || query.id != id) continue;

        dnsUDP.beginPacket(query.clientIP, query.clientPort);
        dnsUDP.write(packet, length);
        dnsUDP.endPacket();
        query.used = false;
        return true;
    }

    return false;
}

void processDNS() {
    expirePending();

    int packetSize;
    while ((packetSize = dnsUDP.parsePacket()) > 0) {
        if (packetSize > DNS_MAX_PACKET) {
            uint8_t discard[32];
            while (dnsUDP.available()) dnsUDP.read(discard, sizeof(discard));
            continue;
        }

        uint8_t packet[DNS_MAX_PACKET];
        int length = dnsUDP.read(packet, sizeof(packet));
        if (length < 12) continue;

        IPAddress remoteIP = dnsUDP.remoteIP();
        uint16_t remotePort = dnsUDP.remotePort();

        // Responses from the upstream resolver are relayed to the original
        // iPad/client. Client queries arrive from the ESPDevLink AP subnet.
        if (dnsStarted && remoteIP != IPAddress(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4) &&
            remoteIP != IPAddress(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4 + 1) &&
            remoteIP == upstreamDNS) {
            if (forwardResponse(packet, static_cast<size_t>(length))) continue;
        }

        uint16_t flags = (static_cast<uint16_t>(packet[2]) << 8) | packet[3];
        uint16_t questions = (static_cast<uint16_t>(packet[4]) << 8) | packet[5];

        if ((flags & 0x8000) != 0 || questions != 1) continue;

        size_t offset = 12;
        String name = readQName(packet, static_cast<size_t>(length), offset);
        if (name.length() == 0 || offset + 4 > static_cast<size_t>(length)) continue;

        // Recovery mode has no upstream DNS, so answer all names locally.
        if (WiFi.status() != WL_CONNECTED || upstreamDNS == IPAddress(0, 0, 0, 0)) {
            answerLocal(packet, static_cast<size_t>(length), remoteIP, remotePort, true);
            continue;
        }

        uint16_t id = (static_cast<uint16_t>(packet[0]) << 8) | packet[1];
        rememberForwardedQuery(id, remoteIP, remotePort);

        dnsUDP.beginPacket(upstreamDNS, DNS_PORT);
        dnsUDP.write(packet, static_cast<size_t>(length));
        dnsUDP.endPacket();
    }
}

void dnsTask(void*) {
    for (;;) {
        if (!dnsStarted) {
            // Wait until the NAT AP has actually been created by main.cpp.
            IPAddress apIP = WiFi.softAPIP();
            if (apIP == IPAddress(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4)) {
                upstreamDNS = WiFi.status() == WL_CONNECTED ? WiFi.dnsIP(0) : IPAddress(0, 0, 0, 0);
                if (WiFi.status() == WL_CONNECTED && upstreamDNS == IPAddress(0, 0, 0, 0)) {
                    upstreamDNS = IPAddress(1, 1, 1, 1);
                }

                if (dnsUDP.begin(DNS_PORT)) {
                    dnsStarted = true;
                    Serial.print("ESPDevLink DNS proxy started on ");
                    Serial.print(IPAddress(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4));
                    Serial.print(":53; upstream DNS: ");
                    if (upstreamDNS == IPAddress(0, 0, 0, 0)) Serial.println("none (recovery mode)");
                    else Serial.println(upstreamDNS);
                }
            }
        } else if (WiFi.softAPIP() != IPAddress(ESPDEVLINK_AP_IP_1, ESPDEVLINK_AP_IP_2, ESPDEVLINK_AP_IP_3, ESPDEVLINK_AP_IP_4)) {
            dnsUDP.stop();
            dnsStarted = false;
        } else {
            // Keep the DNS server alive while the recovery AP is active even
            // when the ESP32 has no upstream Wi-Fi connection.
            if (WiFi.status() == WL_CONNECTED && upstreamDNS == IPAddress(0, 0, 0, 0)) {
                upstreamDNS = WiFi.dnsIP(0);
                if (upstreamDNS == IPAddress(0, 0, 0, 0)) upstreamDNS = IPAddress(1, 1, 1, 1);
            }
            processDNS();
        }

        vTaskDelay(pdMS_TO_TICKS(dnsStarted ? 10 : START_RETRY_MS));
    }
}

struct DNSProxyStarter {
    DNSProxyStarter() {
        xTaskCreate(
            dnsTask,
            "espdevlink_dns",
            4096,
            nullptr,
            1,
            nullptr
        );
    }
};

DNSProxyStarter dnsProxyStarter;

} // namespace
