# Discord alert setup

This project uses a Discord Webhook as a simple bot for door alerts.

## Create the webhook

1. Open Discord and choose your server/channel.
2. Channel Settings -> Integrations -> Webhooks.
3. New Webhook.
4. Name it, for example: `Face Door Alert`.
5. Copy Webhook URL.

Keep the webhook URL private. Anyone with this URL can send messages to that channel.

## Run listener with Discord alerts

Double-click:

```bat
run_face_listener_discord.cmd
```

Paste the webhook URL when asked.

Or run manually in PowerShell:

```powershell
$env:DISCORD_WEBHOOK_URL="PASTE_WEBHOOK_URL_HERE"
python -u .\firebase_face_recognition_listener.py --camera 0 --threshold 70 --frames 10 --duration 10
```

## Alert behavior

- Sends Discord alert when result is `Unknown`.
- Sends Discord alert on recognition errors.
- Does not send message for known faces by default.
- Add `--notify-known` if you also want known-person messages.

Example:

```powershell
python -u .\firebase_face_recognition_listener.py --camera 0 --threshold 70 --frames 10 --duration 10 --discord-webhook $env:DISCORD_WEBHOOK_URL --notify-known
```

## PC sound

The listener also plays a local Windows melody: welcome tune for known faces and warning tune for Unknown. Add --no-sound to disable it.

