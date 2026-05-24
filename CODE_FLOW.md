# CoinDCX Bot Code Flow

This file maps the control flow in `coindcx_ai_bot.py`.

## Top-Level CLI Flow

```mermaid
flowchart TD
    A["python coindcx_ai_bot.py ..."] --> B["main()"]
    B --> C["argparse parses CLI flags"]
    C --> D{"--test-notify?"}
    D -- yes --> E["test_notify()"]
    D -- no --> F{"--loop?"}
    F -- yes --> G["run_loop(confirm_live, max_cycles)"]
    F -- no --> H{"--monitor-position?"}
    H -- yes --> I["monitor_position(...)"]
    H -- no --> J{"--once?"}
    J -- no --> K["Print usage hint; exit 2"]
    J -- yes --> L["run_once(confirm_live)"]
```

## One-Cycle Signal Flow

```mermaid
flowchart TD
    A["run_once(confirm_live)"] --> B["load_config()"]
    B --> C["load_dotenv_if_present()"]
    C --> D["Create BotConfig"]
    D --> E["Create CoinDCXClient"]
    D --> F["Create ConservativeSignalEngine"]
    D --> G["Create Notifier"]
    E --> H["client.get_candles(public_pair, interval, limit)"]
    H --> I["latest_candle_time(candles)"]
    H --> J["latest_candle_age_seconds(candles)"]
    J --> K{"Candle stale or unknown?"}
    K -- yes --> L["Create HOLD Signal confidence=0"]
    L --> M["append_signal_log(... stale_data_hold)"]
    M --> N["Return without order"]
    K -- no --> O["engine.decide(candles)"]
    O --> P["Print signal + latest candle + indicators"]
    P --> Q["Create SignalLogEntry action_taken=hold"]
    Q --> R{"Signal is HOLD or confidence < MIN_CONFIDENCE?"}
    R -- yes --> S["append_signal_log(...)"]
    S --> T{"notifier.should_notify(...)"}
    T -- yes --> U["notifier.send_signal(...)"]
    T -- no --> V["Return without order"]
    U --> V
    R -- no --> W["client.get_orderbook(public_pair)"]
    W --> X["plan_order(config, orderbook, signal)"]
    X --> Y["plan_exits(config, signal.side, entry_price)"]
    Y --> Z{"LIVE_TRADING and --confirm-live?"}
    Z -- no --> AA["Log paper_order_planned"]
    AA --> AB["Maybe notify"]
    AB --> AC["Return without sending order"]
    Z -- yes --> AD["client.create_limit_order(...)"]
    AD --> AE["Log live_entry_order_sent"]
    AE --> AF["Maybe notify"]
    AF --> AG["Return"]
```

## Signal Engine Logic

```mermaid
flowchart TD
    A["ConservativeSignalEngine.decide(candles)"] --> B["candles_chronological(candles)"]
    B --> C["Extract close prices as Decimal"]
    C --> D{"At least 30 closes?"}
    D -- no --> E["Signal(HOLD, 0, Need at least 30 candles)"]
    D -- yes --> F["Calculate RSI from last 15 closes"]
    F --> G["Calculate EMA fast from last 12 closes"]
    G --> H["Calculate EMA slow from last 26 closes"]
    H --> I["Calculate momentum from close[-6] to close[-1]"]
    I --> J{"ema_fast > ema_slow and RSI < 70 and momentum > 0?"}
    J -- yes --> K["Signal(BUY, confidence, indicators)"]
    J -- no --> L{"ema_fast < ema_slow and RSI > 30 and momentum < 0?"}
    L -- yes --> M["Signal(SELL, confidence, indicators)"]
    L -- no --> N["Signal(HOLD, 0.20, indicators)"]
```

## Private API Signing Flow

```mermaid
flowchart TD
    A["create_limit_order(...) or get_balances()"] --> B["_private_post(path, body)"]
    B --> C{"API key and secret present?"}
    C -- no --> D["Raise RuntimeError"]
    C -- yes --> E["Copy body"]
    E --> F["Add timestamp in milliseconds"]
    F --> G["json.dumps(... compact separators)"]
    G --> H["HMAC-SHA256(payload, api_secret)"]
    H --> I["Build POST request"]
    I --> J["Headers: Content-Type, User-Agent, X-AUTH-APIKEY, X-AUTH-SIGNATURE"]
    J --> K["_send(request)"]
    K --> L["Parse JSON response or raise detailed HTTP error"]
```

## Monitor Position Flow

```mermaid
flowchart TD
    A["monitor_position(entry_side, entry_price, quantity, ...)"] --> B["load_config()"]
    B --> C["Create CoinDCXClient"]
    C --> D["plan_exits(config, entry_side, entry_price)"]
    D --> E["Loop until max_checks or forever"]
    E --> F["client.get_orderbook(public_pair)"]
    F --> G["best_price(orderbook, exit_side)"]
    G --> H["round_down(price, price_step)"]
    H --> I["exit_triggered(exit_plan, current_exit_price)"]
    I --> J{"Stop loss or take profit triggered?"}
    J -- no --> K["sleep(monitor_poll_seconds)"]
    K --> E
    J -- yes --> L{"LIVE_TRADING and --confirm-live?"}
    L -- no --> M["Print paper exit; return"]
    L -- yes --> N["client.create_limit_order(exit_side, current_exit_price, quantity)"]
    N --> O["Print live exit response; return"]
```

## Notification Flow

```mermaid
flowchart TD
    A["SignalLogEntry created"] --> B["append_signal_log(config, entry)"]
    A --> C["notifier.should_notify(signal, action_taken)"]
    C --> D{"notify_on"}
    D -- none --> E["Do not notify"]
    D -- all --> F["Notify every signal"]
    D -- actionable --> G{"signal != HOLD or action_taken not in hold set?"}
    G -- no --> E
    G -- yes --> F
    F --> H["notifier.send_signal(entry)"]
    H --> I{"Twilio configured?"}
    I -- yes --> J["_send_twilio_sms(body)"]
    I -- no --> K["Skip SMS"]
    H --> L{"Email configured?"}
    L -- yes --> M["_send_email(subject, body)"]
    L -- no --> N["Skip email"]
```

