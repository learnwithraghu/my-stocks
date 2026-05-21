#!/usr/bin/env python3
"""
Indian ETF analyzer — writes one daily CSV: output/final_output_YYYYMMDD.csv
Only ETFs that pass all recommendation gates (or a single no-buy row).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")

ETF_UNIVERSE = [
    {"ticker": "NIFTYBEES", "name": "Nippon India ETF Nifty 50 BeES"},
    {"ticker": "JUNIORBEES", "name": "Nippon India ETF Junior BeES"},
    {"ticker": "SETFNIF50", "name": "SBI ETF Nifty 50"},
    {"ticker": "HDFCNIFTY", "name": "HDFC Nifty 50 ETF"},
    {"ticker": "HDFCSML250", "name": "HDFC Nifty Smallcap 250 ETF"},
    {"ticker": "BANKBEES", "name": "Nippon India ETF Bank BeES"},
    {"ticker": "ITBEES", "name": "Nippon India ETF Nifty IT"},
    {"ticker": "PHARMABEES", "name": "Nippon India ETF Nifty Pharma"},
    {"ticker": "PSUBNKBEES", "name": "Nippon India ETF PSU Bank BeES"},
    {"ticker": "AUTOBEES", "name": "Nippon India ETF Nifty Auto"},
    {"ticker": "INFRABEES", "name": "Nippon India ETF Nifty Infra"},
    {"ticker": "LOWVOLIETF", "name": "Mirae Asset Nifty 100 Low Volatility ETF"},
    {"ticker": "NV20", "name": "Nippon India ETF NV20"},
    {"ticker": "DIVOPPBEES", "name": "Nippon India ETF Dividend Opportunities"},
    {"ticker": "CONSUMBEES", "name": "Nippon India ETF Nifty Consumption"},
    {"ticker": "GOLDBEES", "name": "Nippon India ETF Gold BeES"},
    {"ticker": "SILVERBEES", "name": "Nippon India ETF Silver BeES"},
    {"ticker": "MON100", "name": "Motilal Oswal Nasdaq 100 ETF"},
    {"ticker": "HNGSNGBEES", "name": "Mirae Asset Hang Seng TECH ETF"},
    {"ticker": "MAFANG", "name": "Mirae Asset NYSE FANG+ ETF"},
    {"ticker": "LIQUIDBEES", "name": "Nippon India ETF Liquid BeES"},
    {"ticker": "GILT5YBEES", "name": "Nippon India ETF 5 Year Gilt"},
    {"ticker": "CPSEETF", "name": "Nippon India ETF CPSE"},
    {"ticker": "MASPTOP50", "name": "Mirae Asset S&P 500 Top 50 ETF"},
    {"ticker": "ICICIB22", "name": "ICICI Prudential Bharat 22 ETF"},
]

BUDGET_INR = 300_000
TRADE_SIZE_INR = 15_000
MAX_SLOTS = BUDGET_INR // TRADE_SIZE_INR  # 20
PROFIT_TARGET_PCT = 3.14

MOM_1M, MOM_3M, MOM_6M, MOM_12M = 21, 63, 126, 252
MIN_HISTORY = MOM_12M + 10
HISTORY_PERIOD = "2y"
RSI_MIN, RSI_MAX = 40, 80
VOL_MIN_FACTOR = 0.70
TURTLE_EXIT_DAYS = 20
PASS_NOTE = "Passes all recommendation gates"

# App safety: trigger must be strictly above (last EOD close − ₹0.06).
# e.g. SILVERBEES EOD ₹252.66 → floor ₹252.60 → min trigger ₹252.61
SAFETY_BELOW_LAST_EOD_INR = 0.06
SAFETY_TICK_ABOVE_FLOOR = 0.01

OUTPUT_COLUMNS = [
    "ticker",
    "todays_last_price_inr",
    "price_as_of",
    "last_eod_close_inr",
    "tomorrow_buy_trigger_inr",
    "profit_target_inr",
    "qty",
    "amount_inr",
    "note",
]


@dataclass
class EtfMetrics:
    ticker: str
    price: float | None
    price_as_of: str | None
    last_eod_close: float | None
    ret_1m: float | None
    ret_3m: float | None
    ret_12m: float | None
    rs_vs_nifty_3m: float | None
    rsi: float | None
    vol_ratio: float | None
    above_exit_zone: bool | None
    recommended: bool
    score: float | None


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def trading_return(closes: pd.Series, days: int) -> float | None:
    if len(closes) <= days:
        return None
    last, old = float(closes.iloc[-1]), float(closes.iloc[-1 - days])
    return round((last - old) / old * 100, 2) if old else None


def rsi(closes: pd.Series, period: int = 14) -> float | None:
    if len(closes) < period + 2:
        return None
    delta = closes.diff().iloc[-period:]
    gains = delta.where(delta > 0, 0.0).sum() / period
    losses = (-delta.where(delta < 0, 0.0)).sum() / period
    if losses == 0:
        return 100.0
    return round(100 - (100 / (1 + gains / losses)), 2)


def fetch_history(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(
            yahoo_symbol(ticker),
            period=HISTORY_PERIOD,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    return df if len(df) >= 10 else None


def fetch_live_price(ticker: str) -> float | None:
    """Latest trade / regular market price (matches broker terminal better than stale EOD bar)."""
    try:
        t = yf.Ticker(yahoo_symbol(ticker))
        live = getattr(t.fast_info, "last_price", None)
        if live is not None and live > 0:
            return round(float(live), 2)
        info = t.info or {}
        for key in ("regularMarketPrice", "currentPrice"):
            v = info.get(key)
            if v is not None and float(v) > 0:
                return round(float(v), 2)
    except Exception:
        pass
    return None


def resolve_todays_price(ticker: str, close: pd.Series) -> tuple[float, str]:
    """
    Prefer Yahoo live quote; fall back to last completed daily close.
    """
    live = fetch_live_price(ticker)
    today_ist = datetime.now(IST).strftime("%Y-%m-%d")
    if live is not None:
        return live, today_ist
    price = round(float(close.iloc[-1]), 2)
    last_dt = close.index[-1]
    price_as_of = pd.Timestamp(last_dt).strftime("%Y-%m-%d")
    return price, price_as_of


def momentum_trigger_price(live_price: float, ret_1m: float | None, ret_3m: float | None) -> float:
    """Raw LIMIT from momentum rules (before app safety floor)."""
    if ret_1m is not None and ret_3m is not None and ret_1m >= ret_3m:
        return round(live_price, 2)
    return round(live_price * 0.998, 2)


def safety_min_trigger(last_eod_close: float) -> tuple[float, float]:
    """
    Broker/app floor: strictly above (last completed EOD close − SAFETY_BELOW_LAST_EOD_INR).
    Returns (floor_label, minimum_allowed_trigger).
    """
    floor = round(last_eod_close - SAFETY_BELOW_LAST_EOD_INR, 2)
    min_trigger = round(floor + SAFETY_TICK_ABOVE_FLOOR, 2)
    return floor, min_trigger


def apply_trigger_with_safety(
    live_price: float, last_eod_close: float, ret_1m: float | None, ret_3m: float | None
) -> tuple[float, float, float]:
    """Returns (final_trigger, safety_floor, safety_min_trigger)."""
    raw = momentum_trigger_price(live_price, ret_1m, ret_3m)
    floor, min_trig = safety_min_trigger(last_eod_close)
    final = round(max(raw, min_trig), 2)
    return final, floor, min_trig


def position_size(trigger: float) -> tuple[int, int]:
    qty = max(1, int(TRADE_SIZE_INR // trigger))
    amount = int(round(qty * trigger))
    if amount > TRADE_SIZE_INR:
        qty = max(1, int(TRADE_SIZE_INR // trigger))
        amount = int(round(qty * trigger))
    return qty, amount


def analyze_one(etf: dict, nifty_3m: float | None) -> EtfMetrics:
    ticker = etf["ticker"]
    df = fetch_history(ticker)
    if df is None or len(df["Close"]) < MIN_HISTORY:
        return EtfMetrics(ticker, None, None, None, None, None, None, None, None, None, None, False, None)

    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]
    last_eod_close = round(float(close.iloc[-1]), 2)
    price, price_as_of = resolve_todays_price(ticker, close)
    r1, r3, r12 = trading_return(close, MOM_1M), trading_return(close, MOM_3M), trading_return(close, MOM_12M)
    rs_val = round(r3 - nifty_3m, 2) if r3 is not None and nifty_3m is not None else None
    rsi_val = rsi(close)
    avg_vol = float(volume.iloc[-21:-1].mean()) if len(volume) > 21 else 0
    vol_ratio = round(float(volume.iloc[-1]) / avg_vol, 2) if avg_vol > 0 else None
    dc_low = float(low.iloc[-(TURTLE_EXIT_DAYS + 1):-1].min()) if len(low) > TURTLE_EXIT_DAYS else None
    above_exit = price > dc_low if dc_low is not None else None

    gates_fail = (
        r12 is None
        or r12 <= 0
        or rs_val is None
        or rs_val <= 0
        or rsi_val is None
        or not (RSI_MIN <= rsi_val <= RSI_MAX)
        or vol_ratio is None
        or vol_ratio < VOL_MIN_FACTOR
        or above_exit is not True
    )
    recommended = not gates_fail
    score = (
        round(r12 * 0.4 + r3 * 0.3 + rs_val * 0.2 + (r1 or 0) * 0.1, 2)
        if recommended and r12 is not None and r3 is not None and rs_val is not None
        else None
    )
    return EtfMetrics(
        ticker,
        price,
        price_as_of,
        last_eod_close,
        r1,
        r3,
        r12,
        rs_val,
        rsi_val,
        vol_ratio,
        above_exit,
        recommended,
        score,
    )


def order_for_pick(m: EtfMetrics) -> tuple[float, float, float, int, int, str]:
    assert m.price is not None and m.last_eod_close is not None
    raw = momentum_trigger_price(m.price, m.ret_1m, m.ret_3m)
    trigger, safety_floor, _ = apply_trigger_with_safety(
        m.price, m.last_eod_close, m.ret_1m, m.ret_3m
    )
    target = round(trigger * (1 + PROFIT_TARGET_PCT / 100), 2)
    qty, amount = position_size(trigger)
    note = PASS_NOTE
    if trigger > raw:
        note = f"{PASS_NOTE}; trigger raised to app safety (> {safety_floor})"
    return trigger, target, qty, amount, safety_floor, note


def build_order_rows(picks: list[EtfMetrics]) -> list[dict]:
    rows = []
    for m in picks:
        trigger, target, qty, amount, _, note = order_for_pick(m)
        rows.append(
            {
                "ticker": m.ticker,
                "todays_last_price_inr": m.price,
                "price_as_of": m.price_as_of or "",
                "last_eod_close_inr": m.last_eod_close,
                "tomorrow_buy_trigger_inr": trigger,
                "profit_target_inr": target,
                "qty": qty,
                "amount_inr": amount,
                "note": note,
            }
        )
    return rows


def write_final_csv(path: Path, picks: list[EtfMetrics]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if picks:
        df = pd.DataFrame(build_order_rows(picks))
    else:
        df = pd.DataFrame(
            [
                {
                    "ticker": "",
                    "todays_last_price_inr": "",
                    "price_as_of": "",
                    "last_eod_close_inr": "",
                    "tomorrow_buy_trigger_inr": "",
                    "profit_target_inr": "",
                    "qty": "",
                    "amount_inr": "",
                    "note": "No ETFs to recommend at this time",
                }
            ]
        )
    df = df[OUTPUT_COLUMNS]
    df.to_csv(path, index=False)
    print(f"Wrote {path} ({len(df)} row(s))")


def cleanup_other_csvs(out_dir: Path, keep: Path) -> None:
    for f in out_dir.glob("*.csv"):
        if f.resolve() != keep.resolve():
            f.unlink()
            print(f"Deleted {f.name}")


def main() -> int:
    root = Path(__file__).resolve().parent
    out_dir = root / "output"
    run_date = datetime.now(IST).strftime("%Y%m%d")
    final_path = out_dir / f"final_output_{run_date}.csv"
    run_at = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")

    print(f"Indian ETF Analyzer | budget ₹{BUDGET_INR:,} | ₹{TRADE_SIZE_INR:,}/trade | target +{PROFIT_TARGET_PCT}%")
    print(f"Run: {run_at}\n")

    nb = fetch_history("NIFTYBEES")
    nifty_3m = trading_return(nb["Close"], MOM_3M) if nb is not None and len(nb["Close"]) > MOM_3M else None
    if nifty_3m is not None:
        print(f"NIFTYBEES 3M: {nifty_3m}%\n")

    metrics = []
    for i, etf in enumerate(ETF_UNIVERSE, 1):
        print(f"[{i}/{len(ETF_UNIVERSE)}] {etf['ticker']}…", end=" ", flush=True)
        m = analyze_one(etf, nifty_3m)
        print("PASS" if m.recommended else "skip")
        metrics.append(m)

    picks = sorted(
        [m for m in metrics if m.recommended and m.score is not None],
        key=lambda x: x.score,
        reverse=True,
    )[:MAX_SLOTS]

    total_deploy = sum(order_for_pick(m)[3] for m in picks if m.price and m.last_eod_close)

    print("\n--- Tomorrow orders (pass gates only) ---")
    if picks:
        for m in picks:
            t, tgt, q, a, floor, _ = order_for_pick(m)
            print(
                f"  {m.ticker}: last ₹{m.price} | EOD ₹{m.last_eod_close} | "
                f"LIMIT ₹{t} | target ₹{tgt} | qty {q} | ₹{a}"
            )
        print(f"  Slots: {len(picks)}/{MAX_SLOTS} | Deploy ~₹{total_deploy:,} of ₹{BUDGET_INR:,}")
    else:
        print("  No ETFs to recommend at this time.")

    write_final_csv(final_path, picks)
    cleanup_other_csvs(out_dir, final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
