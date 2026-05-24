# TradeMaster Joe

## One-Line Description

TradeMaster Joe is a Python-based AI-assisted crypto trading automation project using CoinDCX APIs, paper trading, risk controls, SMS alerts, and cloud deployment through DigitalOcean/systemd.

## Interview Pitch

I built TradeMaster Joe as a controlled trading automation system rather than a blind trading script. It fetches live CoinDCX candle data, checks data freshness, computes RSI/EMA/momentum-based signals, applies confidence and risk gates, logs every signal, sends optional Twilio SMS alerts, and is prepared to run continuously on a DigitalOcean Ubuntu Droplet with systemd.

## Current Capabilities

- CoinDCX public candle and orderbook integration.
- CoinDCX private API signing with HMAC-SHA256.
- Paper trading by default.
- Two-step live trading safety gate: `LIVE_TRADING=true` plus `--confirm-live`.
- Signal generation using RSI, EMA fast/slow, and momentum.
- Stale candle protection with `MAX_CANDLE_AGE_SECONDS`.
- Stop-loss and take-profit exit planning.
- CSV signal logging.
- Twilio SMS notification support.
- DigitalOcean deployment scripts and systemd service.
- GitHub Actions paper-mode workflow for scheduled signal checks before VPS deployment.

## Recommended Droplet

- Ubuntu 24.04 LTS
- DigitalOcean Basic Droplet
- Regular CPU
- 1 GB RAM
- 1 vCPU
- 25 GB SSD
- Bangalore region if available, otherwise Singapore
- SSH key authentication
- Firewall allowing SSH only
- Hostname: `trademaster-joe-01`

## Why This Project Is Presentable

The project demonstrates API integration, secure request signing, environment-based configuration, risk-aware control flow, logging, notifications, cloud deployment, Linux service management, and cautious software design around a high-risk domain.

## Next Engineering Milestones

- Add `analyze_signals.py` for CSV review.
- Add historical backtesting.
- Add order status polling and fill tracking.
- Add position lifecycle management.
- Add daily max loss and kill-switch controls.
- Move from CSV to SQLite/PostgreSQL for long-running deployments.
- Add a lightweight dashboard after the bot is reliable in paper mode.
