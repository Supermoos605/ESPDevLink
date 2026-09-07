# Credentials

## ESP32 firmware

The ESP32 credentials are defined at the top of `src/main.cpp`:

```cpp
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* ACCESS_CODE = "YOUR_ACCESS_CODE";
```

Replace these values only in your local working copy before building and uploading. Do not commit real Wi-Fi credentials or access codes.

If the Wi-Fi placeholders remain unchanged, the firmware starts the fallback access point:

- SSID: `ESPLink-Setup`
- Password: `esp-link-setup`
- Address: `http://192.168.4.1`

The fallback AP password is part of the firmware and is intended only for initial local setup. Change it in `src/main.cpp` if you need a different setup password.

## Windows host

The Windows host uses the `ESPLINK_AUTH_CODE` environment variable. Set it before starting the host:

### Command Prompt

```bat
set ESPLINK_AUTH_CODE=YOUR_ACCESS_CODE
python -m host.host_server
```

### PowerShell

```powershell
$env:ESPLINK_AUTH_CODE="YOUR_ACCESS_CODE"
python -m host.host_server
```

The ESP32 `ACCESS_CODE`, host `ESPLINK_AUTH_CODE`, and simulator `authorization_code` must match when connecting those components together.

## Simulator

The simulator stores its test authorization code in `simulator/config.json`. The committed value is only a placeholder (`CHANGE-ME`). Use a private local change for testing and do not commit a real code.
