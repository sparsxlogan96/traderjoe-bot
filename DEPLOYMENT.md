# Running TradeMaster Joe

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

Recommended DigitalOcean Droplet:

- Image: Ubuntu 24.04 LTS
- Plan: Basic
- CPU option: Regular
- Size: 1 GB RAM, 1 vCPU, 25 GB SSD
- Datacenter: Bangalore if available, otherwise Singapore
- Authentication: SSH key
- Backups: off for now
- Monitoring: on
- Hostname: `trademaster-joe-01`

This size is enough for continuous paper-mode operation through `systemd`.

## Basic Linux Setup

On a fresh Ubuntu server, clone your GitHub repo:

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
git clone https://github.com/YOUR_USERNAME/trademaster-joe.git ~/trademaster-joe
cd ~/trademaster-joe
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

Create `/etc/systemd/system/trademaster-joe.service`:

```ini
[Unit]
Description=TradeMaster Joe paper trading bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trademaster-joe
ExecStart=/usr/bin/python3 /home/ubuntu/trademaster-joe/coindcx_ai_bot.py --loop
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trademaster-joe
sudo systemctl start trademaster-joe
sudo journalctl -u trademaster-joe -f
```

Keep `.env` private. Do not put it in GitHub.

You can also use the included installer:

```bash
bash deploy/install_ubuntu.sh
```
