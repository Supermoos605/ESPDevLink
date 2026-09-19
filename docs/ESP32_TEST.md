# ESPLink ESP32 hardware test

## 1. Configure Wi-Fi

Open `src/main.cpp` and replace:

```cpp
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
```

If these remain unchanged, the firmware starts the fallback access point:

- SSID: `ESPLink-Setup`
- Password: `esp-link-setup`
- Address: `http://192.168.4.1`

## 2. Build and upload

From the repository root:

```bash
pio run
pio run --target upload
pio run --target uploadfs
pio device monitor
```

Use the correct COM port if PlatformIO does not select it automatically.

## 3. Confirm the gateway

After boot, the serial monitor should show:

- `LittleFS mounted.`
- Wi-Fi connected or fallback AP started
- `mDNS available at: http://the printed ESP32 IP address`
- `Web server started.`

Open the printed address in a browser and check:

```text
/api/status
```

The response should contain `status: online`, the Wi-Fi mode, and the mDNS name.

## 4. Confirm the PC heartbeat

Run the Windows host from the `host` directory. The host should send heartbeat data to:

```text
POST /api/pc/heartbeat
```

Then refresh:

```text
/api/pc
```

The `online` field should become `true`.

## 5. First successful milestone

The ESP32 test is successful when:

- The board boots without hanging.
- The browser opens `the printed ESP32 IP address` or the printed IP address.
- `/api/status` reports the gateway online.
- `/api/pc` reports the Windows host online.
- The landing page changes from `OFFLINE` to `ONLINE`.

Real game video requires the later WebRTC host/browser milestone; the ESP32 itself does not run Windows executables.
