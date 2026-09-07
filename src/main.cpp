#include <Arduino.h>

// ESPDevLink firmware entry point.
// Replace the placeholder values below with your local settings in a separate
// credentials header before connecting the device to a network.

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
