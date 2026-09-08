# ESPLink Local Testing Checklist

This checklist is for testing the Windows host and browser interface before connecting an ESP32.

## 1. Prepare the host

1. Open the repository folder in File Explorer.
2. Run `host\\run_esp_link.bat`.
3. Choose **7 — Create virtual environment**.
4. Wait for dependency installation to finish.

## 2. Run automated tests

1. Open the launcher again.
2. Choose **5 — Run tests**.
3. Save any error text if a test fails.

## 3. Start the browser host

1. Choose **1 — Start host server**.
2. Open `http://127.0.0.1:8765/`.
3. Confirm the ESPLink landing page loads.
4. Confirm the page reports the gateway status.

## 4. Check the simulator

1. Stop the host with `Ctrl+C`.
2. Open another launcher window.
3. Choose **3 — Start ESPLink simulator**.
4. Confirm the simulator starts without an import error.

## 5. Later ESP32 testing

After the physical ESP32 is available, repeat the host test while connected to the same network, then replace the loopback address with the ESP32's mDNS address.

> This checklist does not require an ESP32 for the first three sections.
