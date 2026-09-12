# Deploy the free Cloudflare rendezvous service

This service stores only the current Quick Tunnel URL. It does not relay game traffic.

## 1. Create the Worker

In the Cloudflare dashboard, create a Worker named `espdevlink-rendezvous` and deploy `cloudflare-worker.js`.

## 2. Create KV

Create a KV namespace and bind it to the Worker with the binding name `ESPDEVLINK_KV`.

## 3. Add the registration secret

Create a long random secret and add it to the Worker as `REGISTRATION_TOKEN`. Do not commit the secret.

## 4. Get the Worker URL

The Worker will have an HTTPS URL such as `https://espdevlink-rendezvous.<your-subdomain>.workers.dev`.

Use that as `ESPDEVLINK_RENDEZVOUS_URL`.

The Windows Quick Tunnel script also needs `ESPDEVLINK_DEVICE_ID=gaming-pc` and `ESPDEVLINK_RENDEZVOUS_TOKEN=<same secret>`.

## 5. Test

Registering from the Windows PC should produce `[ESPDevLink] Registered gaming-pc with rendezvous service.` The ESP32 can then query `/api/lookup/gaming-pc`.

## Security

Keep `REGISTRATION_TOKEN` private. The lookup endpoint is intentionally public because the ESP32 must be able to reach it without inbound access to the PC.
