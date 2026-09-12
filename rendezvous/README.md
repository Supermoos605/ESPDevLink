# ESPDevLink Rendezvous

Tiny address service for cross-network discovery.

It stores the current HTTPS Cloudflare URL for an ESPDevLink device. It does not carry video, audio, input, or WebRTC media.

## Run

Set a strong token:

    RENDEZVOUS_REGISTRATION_TOKEN=<secret> python server.py

Optional environment variables:

    RENDEZVOUS_BIND=0.0.0.0
    RENDEZVOUS_PORT=8080
    RENDEZVOUS_TTL=120

Publish the service behind HTTPS before using it from the Internet.

## API

The Windows Quick Tunnel helper registers:

    POST /api/register

with:

    Authorization: Bearer <registration-token>

and JSON:

    {"device_id":"gaming-pc","url":"https://example.trycloudflare.com"}

The ESP32 will later use:

    GET /api/lookup/gaming-pc

Records expire automatically after the configured TTL. The Windows helper must refresh the record before it expires when the tunnel remains active.
