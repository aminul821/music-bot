#!/usr/bin/env bash
# Install the bot as a systemd service so it runs 24/7: it keeps running after
# you close the terminal, restarts if it crashes, and starts again after a reboot.
#
#   bash deploy/install-service.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
PYTHON="$APP_DIR/venv/bin/python"
SERVICE=/etc/systemd/system/musicbot.service

if [ ! -x "$PYTHON" ]; then
    echo "❌ $PYTHON not found. Create the venv first:"
    echo "   python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Deno is usually installed per-user in ~/.deno/bin, so add it to the PATH.
USER_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
SERVICE_PATH="$USER_HOME/.deno/bin:$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"

sudo tee "$SERVICE" > /dev/null <<UNIT
[Unit]
Description=Telegram Music Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$SERVICE_PATH
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON -m MusicBot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now musicbot
echo
echo "✅ Music bot is now running 24/7 as a service."
echo "   Logs:     sudo journalctl -u musicbot -f"
echo "   Restart:  sudo systemctl restart musicbot"
echo "   Stop:     sudo systemctl stop musicbot"
echo "   Status:   sudo systemctl status musicbot"
