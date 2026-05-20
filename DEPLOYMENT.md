# Running The Bot

## Local First Run

Install Python 3.11 or newer, then run:

```powershell
python .\coindcx_ai_bot.py --once
```

To watch paper-mode decisions continuously:

```powershell
python .\coindcx_ai_bot.py --loop
```

## Cloud VPS Option

A small Linux VPS is enough for this bot because it only fetches market data and makes simple decisions.

Good simple options:

- DigitalOcean Droplet: simple UI, predictable small server plans.
- AWS Lightsail: good if you already use AWS.
- Oracle Cloud Always Free: can be cheap/free, but free compute capacity can be harder to get and idle resources may be reclaimed.

## Basic Linux Setup

On a fresh Ubuntu server, clone your GitHub repo:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git ~/coindcx-bot
cd ~/coindcx-bot
```

Create `.env`:

```bash
cp .env.example .env
nano .env
```

Run a one-cycle paper test:

```bash
python3 coindcx_ai_bot.py --once
```

Run continuous paper observation:

```bash
python3 coindcx_ai_bot.py --loop
```

## Keeping It Running With systemd

Create `/etc/systemd/system/coindcx-bot.service`:

```ini
[Unit]
Description=CoinDCX paper trading bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/coindcx-bot
ExecStart=/usr/bin/python3 /home/ubuntu/coindcx-bot/coindcx_ai_bot.py --loop
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable coindcx-bot
sudo systemctl start coindcx-bot
sudo journalctl -u coindcx-bot -f
```

Keep `.env` private. Do not put it in GitHub.

You can also use the included installer:

```bash
bash deploy/install_ubuntu.sh
```
