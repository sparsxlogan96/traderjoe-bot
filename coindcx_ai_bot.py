#!/usr/bin/env python3
"""
CoinDCX spot trading bot scaffold.

Default behavior is paper trading. Live order placement requires both:
1. LIVE_TRADING=true in the environment
2. --confirm-live on the command line
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import smtplib
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, ROUND_DOWN
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Any, Literal


SignalSide = Literal["buy", "sell", "hold"]


@dataclasses.dataclass(frozen=True)
class BotConfig:
    api_key: str
    api_secret: str
    public_pair: str
    trading_market: str
    interval: str
    candle_limit: int
    max_quote_per_order: Decimal
    min_confidence: Decimal
    quantity_step: Decimal
    price_step: Decimal
    stop_loss_percent: Decimal
    take_profit_percent: Decimal
    monitor_poll_seconds: int
    loop_sleep_seconds: int
    max_candle_age_seconds: int
    signal_log_path: str
    notify_on: Literal["none", "actionable", "all"]
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    twilio_to_number: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_from: str
    email_to: str
    notification_verbose: bool
    live_trading: bool


@dataclasses.dataclass(frozen=True)
class Signal:
    side: SignalSide
    confidence: Decimal
    reason: str
    rsi: Decimal | None = None
    ema_fast: Decimal | None = None
    ema_slow: Decimal | None = None
    momentum: Decimal | None = None


@dataclasses.dataclass(frozen=True)
class ExitPlan:
    entry_side: Literal["buy", "sell"]
    exit_side: Literal["buy", "sell"]
    stop_loss_price: Decimal
    take_profit_price: Decimal


@dataclasses.dataclass(frozen=True)
class SignalLogEntry:
    timestamp: str
    public_pair: str
    trading_market: str
    interval: str
    signal_side: SignalSide
    confidence: Decimal
    reason: str
    signal: Signal
    last_close: Decimal | None
    candle_time: str
    planned_order: dict[str, Decimal | str] | None
    exit_plan: ExitPlan | None
    live_trading: bool
    action_taken: str


class CoinDCXClient:
    api_base = "https://api.coindcx.com"
    public_base = "https://public.coindcx.com"
    user_agent = "coindcx-ai-bot/0.1"

    def __init__(self, api_key: str, api_secret: str, timeout_seconds: int = 15) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout_seconds = timeout_seconds

    def get_candles(self, pair: str, interval: str, limit: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"pair": pair, "interval": interval, "limit": limit})
        return self._public_get(f"/market_data/candles?{query}")

    def get_orderbook(self, pair: str) -> dict[str, dict[str, str]]:
        query = urllib.parse.urlencode({"pair": pair})
        return self._public_get(f"/market_data/orderbook?{query}")

    def get_balances(self) -> Any:
        return self._private_post("/exchange/v1/users/balances", {})

    def create_limit_order(
        self,
        *,
        market: str,
        side: Literal["buy", "sell"],
        price_per_unit: Decimal,
        total_quantity: Decimal,
    ) -> Any:
        body = {
            "side": side,
            "order_type": "limit_order",
            "market": market,
            "price_per_unit": str(price_per_unit),
            "total_quantity": str(total_quantity),
        }
        return self._private_post("/exchange/v1/orders/create", body)

    def _public_get(self, path: str) -> Any:
        url = f"{self.public_base}{path}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        return self._send(request)

    def _private_post(self, path: str, body: dict[str, Any]) -> Any:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("COINDCX_API_KEY and COINDCX_API_SECRET are required for private APIs.")

        signed_body = dict(body)
        signed_body["timestamp"] = int(round(time.time() * 1000))
        payload = json.dumps(signed_body, separators=(",", ":"))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=payload.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
                "X-AUTH-APIKEY": self.api_key,
                "X-AUTH-SIGNATURE": signature,
            },
            method="POST",
        )
        return self._send(request)

    def _send(self, request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"CoinDCX HTTP {exc.code} for {request.full_url}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error calling CoinDCX: {exc.reason}") from exc


class ConservativeSignalEngine:
    """
    Small local decision engine.

    Treat this as a replaceable AI layer. It deliberately returns HOLD unless
    multiple simple indicators agree, which is preferable while testing.
    """

    def decide(self, candles: list[dict[str, Any]]) -> Signal:
        closes = [Decimal(str(c["close"])) for c in candles_chronological(candles) if "close" in c]
        if len(closes) < 30:
            return Signal("hold", Decimal("0"), "Need at least 30 candles.")

        rsi = self._rsi(closes[-15:])
        ema_fast = self._ema(closes[-12:], Decimal("2") / Decimal("13"))
        ema_slow = self._ema(closes[-26:], Decimal("2") / Decimal("27"))
        momentum = (closes[-1] - closes[-6]) / closes[-6]

        bullish = ema_fast > ema_slow and rsi < Decimal("70") and momentum > Decimal("0")
        bearish = ema_fast < ema_slow and rsi > Decimal("30") and momentum < Decimal("0")

        confidence = min(abs(momentum) * Decimal("20"), Decimal("0.95"))
        if bullish:
            return Signal("buy", confidence, "EMA trend up with positive momentum.", rsi, ema_fast, ema_slow, momentum)
        if bearish:
            return Signal("sell", confidence, "EMA trend down with negative momentum.", rsi, ema_fast, ema_slow, momentum)
        return Signal("hold", Decimal("0.20"), "No strong agreement between EMA trend, RSI, and momentum.", rsi, ema_fast, ema_slow, momentum)

    @staticmethod
    def _ema(values: list[Decimal], alpha: Decimal) -> Decimal:
        ema = values[0]
        for value in values[1:]:
            ema = (value * alpha) + (ema * (Decimal("1") - alpha))
        return ema

    @staticmethod
    def _rsi(values: list[Decimal]) -> Decimal:
        gains: list[Decimal] = []
        losses: list[Decimal] = []
        for previous, current in zip(values, values[1:]):
            delta = current - previous
            gains.append(max(delta, Decimal("0")))
            losses.append(abs(min(delta, Decimal("0"))))

        avg_gain = sum(gains, Decimal("0")) / Decimal(len(gains))
        avg_loss = sum(losses, Decimal("0")) / Decimal(len(losses))
        if avg_loss == 0:
            return Decimal("100")
        relative_strength = avg_gain / avg_loss
        return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def best_price(orderbook: dict[str, dict[str, str]], side: Literal["buy", "sell"]) -> Decimal:
    book_side = "asks" if side == "buy" else "bids"
    prices = [Decimal(price) for price in orderbook.get(book_side, {}).keys()]
    if not prices:
        raise RuntimeError(f"No {book_side} found in orderbook.")
    return min(prices) if side == "buy" else max(prices)


def round_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step


def plan_order(config: BotConfig, orderbook: dict[str, dict[str, str]], signal: Signal) -> dict[str, Decimal | str]:
    if signal.side == "hold":
        raise RuntimeError("Cannot plan order for HOLD signal.")

    price = round_down(best_price(orderbook, signal.side), config.price_step)
    quantity = round_down(config.max_quote_per_order / price, config.quantity_step)
    if quantity <= 0:
        raise RuntimeError("Calculated quantity is zero; increase MAX_QUOTE_PER_ORDER or reduce QUANTITY_STEP.")

    return {
        "side": signal.side,
        "market": config.trading_market,
        "price_per_unit": price,
        "total_quantity": quantity,
        "estimated_quote_value": price * quantity,
    }


def plan_exits(config: BotConfig, entry_side: Literal["buy", "sell"], entry_price: Decimal) -> ExitPlan:
    stop_multiplier = config.stop_loss_percent / Decimal("100")
    profit_multiplier = config.take_profit_percent / Decimal("100")

    if entry_side == "buy":
        stop_loss_price = entry_price * (Decimal("1") - stop_multiplier)
        take_profit_price = entry_price * (Decimal("1") + profit_multiplier)
        exit_side: Literal["buy", "sell"] = "sell"
    else:
        stop_loss_price = entry_price * (Decimal("1") + stop_multiplier)
        take_profit_price = entry_price * (Decimal("1") - profit_multiplier)
        exit_side = "buy"

    return ExitPlan(
        entry_side=entry_side,
        exit_side=exit_side,
        stop_loss_price=round_down(stop_loss_price, config.price_step),
        take_profit_price=round_down(take_profit_price, config.price_step),
    )


def exit_triggered(exit_plan: ExitPlan, current_exit_price: Decimal) -> str | None:
    if exit_plan.entry_side == "buy":
        if current_exit_price <= exit_plan.stop_loss_price:
            return "stop_loss"
        if current_exit_price >= exit_plan.take_profit_price:
            return "take_profit"
    else:
        if current_exit_price >= exit_plan.stop_loss_price:
            return "stop_loss"
        if current_exit_price <= exit_plan.take_profit_price:
            return "take_profit"
    return None


def last_close(candles: list[dict[str, Any]]) -> Decimal | None:
    ordered = candles_chronological(candles)
    if not ordered:
        return None
    newest = ordered[-1]
    if "close" not in newest:
        return None
    return Decimal(str(newest["close"]))


def candles_chronological(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timed = [(candle_timestamp(candle), candle) for candle in candles]
    if all(timestamp is not None for timestamp, _ in timed):
        return [candle for _, candle in sorted(timed, key=lambda item: item[0] or 0)]
    return list(reversed(candles))


def candle_timestamp(candle: dict[str, Any]) -> int | None:
    for key in ("time", "timestamp", "T", "t"):
        if key in candle:
            try:
                return int(candle[key])
            except (TypeError, ValueError):
                return None
    return None


def latest_candle_time(candles: list[dict[str, Any]]) -> str:
    ordered = candles_chronological(candles)
    if not ordered:
        return "unknown"

    timestamp = candle_timestamp(ordered[-1])
    if timestamp is None:
        return "unknown"

    seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def latest_candle_age_seconds(candles: list[dict[str, Any]]) -> int | None:
    ordered = candles_chronological(candles)
    if not ordered:
        return None

    timestamp = candle_timestamp(ordered[-1])
    if timestamp is None:
        return None

    seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    return int(time.time() - seconds)


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"


def format_indicators(signal: Signal) -> str:
    parts = []
    if signal.rsi is not None:
        parts.append(f"RSI={signal.rsi:.2f}")
    if signal.ema_fast is not None:
        parts.append(f"EMA_fast={signal.ema_fast:.2f}")
    if signal.ema_slow is not None:
        parts.append(f"EMA_slow={signal.ema_slow:.2f}")
    if signal.momentum is not None:
        parts.append(f"momentum={signal.momentum:.4%}")
    return ", ".join(parts)


def decimal_json(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def append_signal_log(config: BotConfig, entry: SignalLogEntry) -> None:
    row = {
        "timestamp": entry.timestamp,
        "public_pair": entry.public_pair,
        "trading_market": entry.trading_market,
        "interval": entry.interval,
        "signal_side": entry.signal_side,
        "confidence": str(entry.confidence),
        "reason": entry.reason,
        "rsi": "" if entry.signal.rsi is None else str(entry.signal.rsi),
        "ema_fast": "" if entry.signal.ema_fast is None else str(entry.signal.ema_fast),
        "ema_slow": "" if entry.signal.ema_slow is None else str(entry.signal.ema_slow),
        "momentum": "" if entry.signal.momentum is None else str(entry.signal.momentum),
        "last_close": "" if entry.last_close is None else str(entry.last_close),
        "candle_time": entry.candle_time,
        "planned_order": "" if entry.planned_order is None else json.dumps(entry.planned_order, default=decimal_json),
        "exit_plan": "" if entry.exit_plan is None else json.dumps(dataclasses.asdict(entry.exit_plan), default=decimal_json),
        "live_trading": str(entry.live_trading),
        "action_taken": entry.action_taken,
    }
    file_exists = os.path.exists(config.signal_log_path)
    fieldnames = list(row.keys())
    write_header = not file_exists
    if file_exists:
        with open(config.signal_log_path, "r", newline="", encoding="utf-8") as file:
            existing_header = file.readline().strip().split(",")
            write_header = existing_header != fieldnames

    with open(config.signal_log_path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


class Notifier:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def should_notify(self, signal: Signal, action_taken: str) -> bool:
        if self.config.notify_on == "none":
            return False
        if self.config.notify_on == "all":
            return True
        return signal.side != "hold" or action_taken not in {"hold", "paper_hold"}

    def send_signal(self, entry: SignalLogEntry) -> None:
        subject = f"CoinDCX bot signal: {entry.signal_side.upper()} {entry.public_pair}"
        body = self._format_signal(entry)
        errors: list[str] = []

        if self._twilio_enabled():
            if self.config.notification_verbose:
                print("Twilio SMS: enabled, sending message...")
            try:
                self._send_twilio_sms(body)
                if self.config.notification_verbose:
                    print("Twilio SMS: sent request successfully.")
            except Exception as exc:
                errors.append(f"Twilio SMS failed: {exc}")
        else:
            if self.config.notification_verbose:
                print("Twilio SMS: disabled or missing configuration.")

        if self._email_enabled():
            if self.config.notification_verbose:
                print("Email: enabled, sending message...")
            try:
                self._send_email(subject, body)
                if self.config.notification_verbose:
                    print("Email: sent successfully.")
            except Exception as exc:
                errors.append(f"Email failed: {exc}")
        else:
            if self.config.notification_verbose:
                print("Email: disabled or missing configuration.")

        for error in errors:
            print(error, file=sys.stderr)

    def _format_signal(self, entry: SignalLogEntry) -> str:
        lines = [
            f"CoinDCX signal: {entry.signal_side.upper()}",
            f"Pair: {entry.public_pair}",
            f"Confidence: {entry.confidence}",
            f"Last close: {entry.last_close}",
            f"Candle time: {entry.candle_time}",
            f"Action: {entry.action_taken}",
            f"Reason: {entry.reason}",
        ]
        indicators = format_indicators(entry.signal)
        if indicators:
            lines.append(f"Indicators: {indicators}")
        if entry.planned_order is not None:
            lines.append(f"Planned order: {json.dumps(entry.planned_order, default=decimal_json)}")
        if entry.exit_plan is not None:
            lines.append(f"Exit plan: {json.dumps(dataclasses.asdict(entry.exit_plan), default=decimal_json)}")
        return "\n".join(lines)

    def _twilio_enabled(self) -> bool:
        return all(
            [
                self.config.twilio_account_sid,
                self.config.twilio_auth_token,
                self.config.twilio_from_number,
                self.config.twilio_to_number,
            ]
        )

    def _send_twilio_sms(self, body: str) -> None:
        account_sid = self.config.twilio_account_sid
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = urllib.parse.urlencode(
            {
                "From": self.config.twilio_from_number,
                "To": self.config.twilio_to_number,
                "Body": body[:1500],
            }
        ).encode("utf-8")
        request = urllib.request.Request(url, data=payload, method="POST")
        auth = f"{account_sid}:{self.config.twilio_auth_token}".encode("utf-8")
        request.add_header("Authorization", f"Basic {base64_encode(auth)}")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Twilio HTTP {exc.code}: {raw}") from exc

    def _email_enabled(self) -> bool:
        return all([self.config.smtp_host, self.config.email_from, self.config.email_to])

    def _send_email(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.email_from
        message["To"] = self.config.email_to
        message.set_content(body)

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                smtp.login(self.config.smtp_username, self.config.smtp_password)
            smtp.send_message(message)


def base64_encode(value: bytes) -> str:
    import base64

    return base64.b64encode(value).decode("ascii")


def load_config() -> BotConfig:
    load_dotenv_if_present()
    notify_on = os.getenv("NOTIFY_ON", "none").lower()
    if notify_on not in {"none", "actionable", "all"}:
        raise RuntimeError("NOTIFY_ON must be one of: none, actionable, all.")

    return BotConfig(
        api_key=os.getenv("COINDCX_API_KEY", ""),
        api_secret=os.getenv("COINDCX_API_SECRET", ""),
        public_pair=os.getenv("COINDCX_PUBLIC_PAIR", "B-BTC_USDT"),
        trading_market=os.getenv("COINDCX_TRADING_MARKET", "BTCUSDT"),
        interval=os.getenv("CANDLE_INTERVAL", "5m"),
        candle_limit=int(os.getenv("CANDLE_LIMIT", "100")),
        max_quote_per_order=Decimal(os.getenv("MAX_QUOTE_PER_ORDER", "10")),
        min_confidence=Decimal(os.getenv("MIN_CONFIDENCE", "0.60")),
        quantity_step=Decimal(os.getenv("QUANTITY_STEP", "0.000001")),
        price_step=Decimal(os.getenv("PRICE_STEP", "0.01")),
        stop_loss_percent=Decimal(os.getenv("STOP_LOSS_PERCENT", "1.50")),
        take_profit_percent=Decimal(os.getenv("TAKE_PROFIT_PERCENT", "3.00")),
        monitor_poll_seconds=int(os.getenv("MONITOR_POLL_SECONDS", "15")),
        loop_sleep_seconds=int(os.getenv("LOOP_SLEEP_SECONDS", "300")),
        max_candle_age_seconds=int(os.getenv("MAX_CANDLE_AGE_SECONDS", "900")),
        signal_log_path=os.getenv("SIGNAL_LOG_PATH", "signals.csv"),
        notify_on=notify_on,  # type: ignore[arg-type]
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
        twilio_to_number=os.getenv("TWILIO_TO_NUMBER", ""),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        email_from=os.getenv("EMAIL_FROM", os.getenv("SMTP_USERNAME", "")),
        email_to=os.getenv("EMAIL_TO", ""),
        notification_verbose=os.getenv("NOTIFICATION_VERBOSE", "false").lower() == "true",
        live_trading=os.getenv("LIVE_TRADING", "false").lower() == "true",
    )


def load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def run_once(confirm_live: bool) -> int:
    config = load_config()
    client = CoinDCXClient(config.api_key, config.api_secret)
    engine = ConservativeSignalEngine()
    notifier = Notifier(config)

    candles = client.get_candles(config.public_pair, config.interval, config.candle_limit)
    candle_time = latest_candle_time(candles)
    candle_age = latest_candle_age_seconds(candles)

    if candle_age is None or candle_age > config.max_candle_age_seconds:
        signal = Signal(
            "hold",
            Decimal("0"),
            f"Stale candle data; latest candle age is {format_duration(candle_age)}.",
        )
        print(f"Signal: {signal.side.upper()} confidence={signal.confidence} reason={signal.reason}")
        print(f"Latest candle: close={last_close(candles)} time={candle_time} age={format_duration(candle_age)}")

        log_entry = SignalLogEntry(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            public_pair=config.public_pair,
            trading_market=config.trading_market,
            interval=config.interval,
            signal_side=signal.side,
            confidence=signal.confidence,
            reason=signal.reason,
            signal=signal,
            last_close=last_close(candles),
            candle_time=candle_time,
            planned_order=None,
            exit_plan=None,
            live_trading=False,
            action_taken="stale_data_hold",
        )
        append_signal_log(config, log_entry)
        print("No order: candle data is stale. Check COINDCX_PUBLIC_PAIR or candle endpoint before trading.")
        return 0

    signal = engine.decide(candles)
    print(f"Signal: {signal.side.upper()} confidence={signal.confidence} reason={signal.reason}")
    print(f"Latest candle: close={last_close(candles)} time={candle_time} age={format_duration(candle_age)}")
    indicators = format_indicators(signal)
    if indicators:
        print(f"Indicators: {indicators}")

    log_entry = SignalLogEntry(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        public_pair=config.public_pair,
        trading_market=config.trading_market,
        interval=config.interval,
        signal_side=signal.side,
        confidence=signal.confidence,
        reason=signal.reason,
        signal=signal,
        last_close=last_close(candles),
        candle_time=candle_time,
        planned_order=None,
        exit_plan=None,
        live_trading=config.live_trading and confirm_live,
        action_taken="hold",
    )

    if signal.side == "hold" or signal.confidence < config.min_confidence:
        print("No order: signal is HOLD or below MIN_CONFIDENCE.")
        append_signal_log(config, log_entry)
        if notifier.should_notify(signal, log_entry.action_taken):
            notifier.send_signal(log_entry)
        return 0

    orderbook = client.get_orderbook(config.public_pair)
    order = plan_order(config, orderbook, signal)
    print("Planned order:")
    print(json.dumps({key: str(value) for key, value in order.items()}, indent=2))
    exit_plan = plan_exits(config, signal.side, Decimal(str(order["price_per_unit"])))
    print("Planned exits after entry fill:")
    print(json.dumps(dataclasses.asdict(exit_plan), indent=2, default=str))

    if not (config.live_trading and confirm_live):
        print("Paper mode: order was not sent. Set LIVE_TRADING=true and pass --confirm-live to trade.")
        log_entry = dataclasses.replace(
            log_entry,
            planned_order=order,
            exit_plan=exit_plan,
            action_taken="paper_order_planned",
        )
        append_signal_log(config, log_entry)
        if notifier.should_notify(signal, log_entry.action_taken):
            notifier.send_signal(log_entry)
        return 0

    response = client.create_limit_order(
        market=str(order["market"]),
        side=signal.side,
        price_per_unit=Decimal(str(order["price_per_unit"])),
        total_quantity=Decimal(str(order["total_quantity"])),
    )
    print("Live order response:")
    print(json.dumps(response, indent=2))
    print("Important: monitor the entry fill on CoinDCX before starting an exit monitor.")
    log_entry = dataclasses.replace(
        log_entry,
        planned_order=order,
        exit_plan=exit_plan,
        action_taken="live_entry_order_sent",
    )
    append_signal_log(config, log_entry)
    if notifier.should_notify(signal, log_entry.action_taken):
        notifier.send_signal(log_entry)
    return 0


def test_notify() -> int:
    config = load_config()
    notifier = Notifier(config)
    signal = Signal("hold", Decimal("0.00"), "Notification test from local bot.")
    entry = SignalLogEntry(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        public_pair=config.public_pair,
        trading_market=config.trading_market,
        interval=config.interval,
        signal_side=signal.side,
        confidence=signal.confidence,
        reason=signal.reason,
        signal=signal,
        last_close=None,
        candle_time="test",
        planned_order=None,
        exit_plan=None,
        live_trading=False,
        action_taken="test_notification",
    )
    append_signal_log(config, entry)
    notifier.send_signal(entry)
    print("Test notification attempted. Check SMS/email and any error output above.")
    return 0


def run_loop(confirm_live: bool, max_cycles: int | None) -> int:
    config = load_config()
    if config.live_trading or confirm_live:
        print("Loop mode is paper-only. Use --once for live entries, then --monitor-position for exits.", file=sys.stderr)
        return 2

    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        cycle += 1
        print(f"\nCycle {cycle} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        result = run_once(confirm_live=False)
        if result != 0:
            return result
        time.sleep(config.loop_sleep_seconds)

    print("Loop ended.")
    return 0


def monitor_position(
    *,
    entry_side: Literal["buy", "sell"],
    entry_price: Decimal,
    quantity: Decimal,
    confirm_live: bool,
    max_checks: int | None,
) -> int:
    config = load_config()
    client = CoinDCXClient(config.api_key, config.api_secret)
    exit_plan = plan_exits(config, entry_side, entry_price)

    print("Monitoring filled position:")
    print(json.dumps(dataclasses.asdict(exit_plan), indent=2, default=str))

    checks = 0
    while max_checks is None or checks < max_checks:
        checks += 1
        orderbook = client.get_orderbook(config.public_pair)
        current_exit_price = round_down(best_price(orderbook, exit_plan.exit_side), config.price_step)
        trigger = exit_triggered(exit_plan, current_exit_price)
        print(f"Check {checks}: exit_side={exit_plan.exit_side} price={current_exit_price} trigger={trigger or 'none'}")

        if trigger is not None:
            if not (config.live_trading and confirm_live):
                print(f"Paper mode: would exit because {trigger} triggered.")
                return 0

            response = client.create_limit_order(
                market=config.trading_market,
                side=exit_plan.exit_side,
                price_per_unit=current_exit_price,
                total_quantity=round_down(quantity, config.quantity_step),
            )
            print("Live exit order response:")
            print(json.dumps(response, indent=2))
            return 0

        time.sleep(config.monitor_poll_seconds)

    print("Monitor ended without an exit trigger.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CoinDCX AI-assisted spot trading scaffold.")
    parser.add_argument("--once", action="store_true", help="Run one decision cycle.")
    parser.add_argument("--loop", action="store_true", help="Run paper-mode decision cycles continuously.")
    parser.add_argument("--max-cycles", type=int, help="Stop --loop after this many cycles.")
    parser.add_argument("--test-notify", action="store_true", help="Send a test Twilio/email notification.")
    parser.add_argument("--monitor-position", choices=["buy", "sell"], help="Monitor a filled position for stop-loss/take-profit exit.")
    parser.add_argument("--entry-price", type=Decimal, help="Filled entry price for --monitor-position.")
    parser.add_argument("--quantity", type=Decimal, help="Filled quantity for --monitor-position.")
    parser.add_argument("--max-checks", type=int, help="Stop monitor after this many price checks.")
    parser.add_argument("--confirm-live", action="store_true", help="Required in addition to LIVE_TRADING=true.")
    args = parser.parse_args()

    if args.test_notify:
        try:
            return test_notify()
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.loop:
        return run_loop(confirm_live=args.confirm_live, max_cycles=args.max_cycles)

    if args.monitor_position:
        if args.entry_price is None or args.quantity is None:
            print("--monitor-position requires --entry-price and --quantity.", file=sys.stderr)
            return 2
        try:
            return monitor_position(
                entry_side=args.monitor_position,
                entry_price=args.entry_price,
                quantity=args.quantity,
                confirm_live=args.confirm_live,
                max_checks=args.max_checks,
            )
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if not args.once:
        print("Use --once to run one decision cycle. Continuous trading should be added only after paper testing.")
        return 2

    try:
        return run_once(confirm_live=args.confirm_live)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
