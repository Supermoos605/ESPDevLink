#include <Arduino.h>

// ESPDevLink firmware entry point.
//
// This file intentionally uses placeholders so the repository contains no
// Wi-Fi credentials or access codes. Replace these values only in your local
// working copy before building the firmware.

namespace config {
constexpr const char* WIFI_SSID = "YOUR_WIFI_NAME";
constexpr const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
constexpr const char* ACCESS_CODE = "YOUR_ACCESS_CODE";
}

void setup() {
  Serial.begin(115200);
  delay(250);

  Serial.println();
  Serial.println("ESPDevLink starting...");
  Serial.println("Wi-Fi credentials are placeholders.");
}

void loop() {
  // Firmware functionality will be added here.
  delay(1000);
}
