#pragma once

// Copy this file to include/espdevlink_secrets.h and replace the placeholders.
// The real file is ignored by Git.

#define ESPDEVLINK_WIFI_SSID "YOUR_WIFI_NAME"
#define ESPDEVLINK_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Optional secondary network. If the primary network cannot be reached at boot,
// ESPDevLink will try this network before starting the ESPLink-Setup AP.
#define ESPDEVLINK_FALLBACK_WIFI_SSID "YOUR_FALLBACK_WIFI_NAME"
#define ESPDEVLINK_FALLBACK_WIFI_PASSWORD "YOUR_FALLBACK_WIFI_PASSWORD"

// ESPDevLink client network. This is the Wi-Fi network the iPad/phone joins.
// Keep it different from the upstream Wi-Fi credentials above.
#define ESPDEVLINK_AP_SSID "ESPDevLink"
#define ESPDEVLINK_AP_PASSWORD "CHANGE_ME_TO_AN_AP_PASSWORD"

#define ESPDEVLINK_ACCESS_CODE "YOUR_ACCESS_CODE"
#define ESPDEVLINK_KEYVAL_KEY "CHANGE_ME_TO_A_LONG_RANDOM_KEY"
