# TradeMaster Joe GitHub And DigitalOcean Checklist

## Before Pushing To GitHub

- Confirm `.env` is not committed.
- Confirm `signals.csv` is not committed.
- Keep `LIVE_TRADING=false` in any shared examples.
- Push only code, docs, and templates.

Useful commands:

```powershell
git status --short
git add coindcx_ai_bot.py README.md DEPLOYMENT.md .env.example .gitignore requirements.txt deploy GITHUB_DEPLOYMENT_CHECKLIST.md PROJECT_BRIEF.md CODE_FLOW.md
git commit -m "Prepare TradeMaster Joe for cloud deployment"
```

If Git reports dubious ownership on this folder, run:

```powershell
git config --global --add safe.directory "C:/Users/spars/Documents/Codex/2026-05-19/i-want-to-write-a-python"
```

Then create an empty GitHub repo and push:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/trademaster-joe.git
git push -u origin main
```

## DigitalOcean Droplet

Recommended starting point:

- Ubuntu LTS
- Basic shared CPU Droplet, regular CPU, 1 GB RAM, 1 vCPU, 25 GB SSD
- SSH key authentication
- Firewall allowing SSH only
- Hostname: `trademaster-joe-01`

After the Droplet is ready:

```bash
ssh ubuntu@YOUR_DROPLET_IP
git clone https://github.com/YOUR_USERNAME/trademaster-joe.git ~/trademaster-joe
cd ~/trademaster-joe
bash deploy/install_ubuntu.sh
```

Edit `.env`:

```bash
nano .env
```

Run a paper test:

```bash
python3 coindcx_ai_bot.py --once
```

Start continuous paper observation:

```bash
sudo systemctl enable trademaster-joe
sudo systemctl start trademaster-joe
sudo journalctl -u trademaster-joe -f
```

Stop it:

```bash
sudo systemctl stop trademaster-joe
```
