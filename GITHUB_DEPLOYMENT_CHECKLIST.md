# GitHub And DigitalOcean Checklist

## Before Pushing To GitHub

- Confirm `.env` is not committed.
- Confirm `signals.csv` is not committed.
- Keep `LIVE_TRADING=false` in any shared examples.
- Push only code, docs, and templates.

Useful commands:

```powershell
git status --short
git add coindcx_ai_bot.py README.md DEPLOYMENT.md .env.example .gitignore requirements.txt deploy GITHUB_DEPLOYMENT_CHECKLIST.md
git commit -m "Add CoinDCX paper trading bot"
```

If Git reports dubious ownership on this folder, run:

```powershell
git config --global --add safe.directory "C:/Users/spars/Documents/Codex/2026-05-19/i-want-to-write-a-python"
```

Then create an empty GitHub repo and push:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## DigitalOcean Droplet

Recommended starting point:

- Ubuntu LTS
- Basic shared CPU Droplet
- SSH key authentication
- Firewall allowing SSH only

After the Droplet is ready:

```bash
ssh ubuntu@YOUR_DROPLET_IP
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git ~/coindcx-bot
cd ~/coindcx-bot
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
sudo systemctl enable coindcx-bot
sudo systemctl start coindcx-bot
sudo journalctl -u coindcx-bot -f
```

Stop it:

```bash
sudo systemctl stop coindcx-bot
```
