# Remote sharing helper

`remote_share.py` starts a Cloudflare Quick Tunnel for the ESPDevLink host and emails the temporary URL through Gmail.

## Requirements

- Windows host running ESPDevLink on port 8765.
- `cloudflared` installed and available on PATH.
- A Gmail account with 2-Step Verification enabled.
- A Gmail App Password for SMTP.

## Windows environment variables

PowerShell:

    $env:ESPDEVLINK_EMAIL_FROM="yourgmail@gmail.com"
    $env:ESPDEVLINK_EMAIL_TO="recipient@example.com"
    $env:ESPDEVLINK_GMAIL_APP_PASSWORD="your-16-character-app-password"

Then run:

    python tools/remote_share.py

Do not put the app password in the repository, a source file, or a command that will be committed.

The script creates a temporary `trycloudflare.com` URL and publishes it to the configured KeyVal rendezvous entry. The URL stops working when the script stops.

## Security

Anyone who obtains the temporary URL can reach the published ESPDevLink HTTP endpoint, so ESPDevLink authorization must remain enabled. Do not email or commit the Gmail app password.
