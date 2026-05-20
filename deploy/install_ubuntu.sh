#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/coindcx-bot}"
SERVICE_NAME="${SERVICE_NAME:-coindcx-bot}"

sudo apt update
sudo apt install -y python3 python3-venv git

cd "$APP_DIR"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it before starting the service:"
  echo "  nano $APP_DIR/.env"
fi

python3 -m py_compile coindcx_ai_bot.py
python3 coindcx_ai_bot.py --test-notify || true

sudo cp deploy/coindcx-bot.service "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload

echo
echo "Install complete. Next:"
echo "  nano $APP_DIR/.env"
echo "  python3 $APP_DIR/coindcx_ai_bot.py --once"
echo "  sudo systemctl enable ${SERVICE_NAME}"
echo "  sudo systemctl start ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
