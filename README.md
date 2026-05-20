# CoinDCX AI Trading Bot Scaffold

This is a cautious Python starter for an AI-assisted CoinDCX spot trading bot. It is paper-only by default.

## Why It Is Conservative

Crypto trading is high risk. The bot will not place live orders unless both safeguards are enabled:

```powershell
$env:LIVE_TRADING="true"
python .\coindcx_ai_bot.py --once --confirm-live
```

Without both, it prints the planned order and stops.

Every planned entry also prints stop-loss and take-profit levels. These defaults can be changed in `.env`:

```env
STOP_LOSS_PERCENT=1.50
TAKE_PROFIT_PERCENT=3.00
MONITOR_POLL_SECONDS=15
MAX_CANDLE_AGE_SECONDS=900
```

The bot refuses to trade if the latest candle is older than `MAX_CANDLE_AGE_SECONDS`.

## Setup

Copy `.env.example` to `.env`, fill in your values, then run:

```powershell
python .\coindcx_ai_bot.py --once
```

The script uses only the Python standard library.

To observe paper-mode decisions continuously:

```powershell
python .\coindcx_ai_bot.py --loop
```

Loop mode is intentionally paper-only. Use `--once` for a reviewed live entry, then `--monitor-position` after that entry fills.

## Logs And Notifications

Every signal is saved to `signals.csv` by default. Change the path in `.env`:

```env
SIGNAL_LOG_PATH=signals.csv
```

Notifications are disabled by default. To receive every signal:

```env
NOTIFY_ON=all
```

To receive only actionable signals where the bot plans or sends an order:

```env
NOTIFY_ON=actionable
```

To show successful SMS/email send status in the console:

```env
NOTIFICATION_VERBOSE=true
```

Leave it as `false` for cleaner loop output.

For Twilio SMS, fill these in:

```env
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+919876543210
```

For email, fill these in:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=destination_email@example.com
```

Send a notification test:

```powershell
python .\coindcx_ai_bot.py --test-notify
```

## Monitoring A Filled Position

After a limit entry fills on CoinDCX, you can monitor that position for stop-loss or take-profit:

```powershell
python .\coindcx_ai_bot.py --monitor-position buy --entry-price 65000 --quantity 0.0001
```

This is paper mode unless live trading is explicitly enabled:

```powershell
$env:LIVE_TRADING="true"
python .\coindcx_ai_bot.py --monitor-position buy --entry-price 65000 --quantity 0.0001 --confirm-live
```

For a filled `buy`, the monitor exits with a `sell`. For a filled `sell`, it exits with a `buy`.

## How The Signal Works

`ConservativeSignalEngine` is the AI layer placeholder. Right now it combines EMA trend, RSI, and momentum and returns `BUY`, `SELL`, or `HOLD` with confidence. Replace that class with your own model only after you have:

- backtested it,
- checked exchange fees and minimum quantities,
- set strict max order sizes,
- added stop-loss or exit logic,
- run paper mode for long enough to see bad market conditions.

## CoinDCX API Notes

CoinDCX private calls require a timestamp in the JSON body. The compact JSON payload is signed with HMAC-SHA256 using your API secret and sent with `X-AUTH-APIKEY` and `X-AUTH-SIGNATURE`.

Public market data comes from `https://public.coindcx.com`; private account and order endpoints come from `https://api.coindcx.com`.
