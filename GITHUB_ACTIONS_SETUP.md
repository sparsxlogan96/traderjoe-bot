# GitHub Actions Paper-Mode Setup

TradeMaster Joe can run one paper-mode signal check on GitHub Actions every 15 minutes. This is useful before you have a VPS.

## What This Does

- Runs `python coindcx_ai_bot.py --once`
- Uses GitHub Secrets and Variables instead of `.env`
- Forces `LIVE_TRADING=false`
- Uploads `signals.csv` as a workflow artifact
- Can be run manually from the GitHub Actions tab

## What This Does Not Do

- It does not run continuously like a VPS.
- It does not guarantee exact 15-minute timing.
- It should not be used for live trading or stop-loss monitoring.

## Required Repository Secrets

Go to:

```text
GitHub repo -> Settings -> Secrets and variables -> Actions -> Secrets
```

Add:

```text
COINDCX_API_KEY
COINDCX_API_SECRET
```

For Twilio SMS, add:

```text
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER
TWILIO_TO_NUMBER
```

Email secrets are optional:

```text
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
EMAIL_FROM
EMAIL_TO
```

## Optional Repository Variables

Go to:

```text
GitHub repo -> Settings -> Secrets and variables -> Actions -> Variables
```

Useful variables:

```text
COINDCX_PUBLIC_PAIR=I-BTC_INR
COINDCX_TRADING_MARKET=BTCINR
CANDLE_INTERVAL=5m
CANDLE_LIMIT=100
MIN_CONFIDENCE=0.60
MAX_CANDLE_AGE_SECONDS=900
NOTIFY_ON=actionable
NOTIFICATION_VERBOSE=false
```

If you do not add these variables, the workflow uses safe defaults.

## Manual Test

After pushing the workflow:

1. Open the GitHub repo.
2. Go to `Actions`.
3. Select `TradeMaster Joe Paper Signal`.
4. Click `Run workflow`.
5. Open the run logs and verify the signal output.

## Important Safety Note

The workflow hard-codes:

```text
LIVE_TRADING=false
```

Do not change that for GitHub Actions. GitHub Actions is for paper observation only.
