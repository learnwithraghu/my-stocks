#!/usr/bin/env python3
"""
German stock screener — Turtle trading + Dual Momentum (.agent/turtle-dual-momentum).
Output: output/final_output_YYYYMMDD.csv (passing stocks only).
One-time budget: $50 USD per pick (fractional shares allowed) — same buy logic as US stock.
Prices on XETRA are EUR; gates use EUR, sizing/CSV amounts use USD via EUR/USD.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from de_universe import GERMAN_STOCK_TICKERS

CET = ZoneInfo("Europe/Berlin")
BENCHMARK = "EXS1"
BUDGET_USD = 50
TRADE_SIZE_USD = 50
FRACTIONAL_QTY_DECIMALS = 6
PROFIT_TARGET_PCT = 3.14
YAHOO_SUFFIX = ".DE"
FX_PAIR = "EURUSD=X"

TURTLE_ENTRY_DAYS = 55
TURTLE_EXIT_DAYS = 20
MOM_1M, MOM_3M, MOM_6M, MOM_12M = 21, 63, 126, 252
MIN_HISTORY = MOM_12M + 10
HISTORY_PERIOD = "2y"
RSI_MIN, RSI_MAX = 40, 80
VOL_MIN_FACTOR = 0.70
SAFETY_BELOW_LAST_EOD = 0.01
SAFETY_TICK_ABOVE_FLOOR = 0.01
PASS_NOTE = "Passes all recommendation gates"
NO_PICKS_NOTE = "No stocks to recommend at this time"

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
class StockPick:
    ticker: str
    price: float
    price_as_of: str
    last_eod: float
    trigger: float
    target: float
    qty: float
    amount: float
    note: str
    score: float


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}{YAHOO_SUFFIX}"


def eur_to_usd(amount_eur: float, eurusd: float) -> float:
    return round(amount_eur * eurusd, 2)


def fetch_eurusd() -> float | None:
    try:
        t = yf.Ticker(FX_PAIR)
        p = getattr(t.fast_info, "last_price", None)
        if p is not None and float(p) > 0:
            return round(float(p), 4)
        for key in ("regularMarketPrice", "currentPrice"):
            v = (t.info or {}).get(key)
            if v is not None and float(v) > 0:
                return round(float(v), 4)
        df = yf.download(FX_PAIR, period="5d", interval="1d", progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return round(float(df["Close"].iloc[-1]), 4)
    except Exception as e:
        print(f"  [warn] EUR/USD: {e}", file=sys.stderr)
    return None


def ret_pct(closes: pd.Series, days: int) -> float | None:
    if len(closes) <= days:
        return None
    a, b = float(closes.iloc[-1]), float(closes.iloc[-1 - days])
    return round((a - b) / b * 100, 2) if b else None


def rsi14(closes: pd.Series) -> float | None:
    if len(closes) < 16:
        return None
    d = closes.diff().iloc[-14:]
    g, l = d.where(d > 0, 0.0).sum() / 14, (-d.where(d < 0, 0.0)).sum() / 14
    return 100.0 if l == 0 else round(100 - 100 / (1 + g / l), 2)


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
    return df if len(df) >= MIN_HISTORY else None


def live_price(ticker: str) -> float | None:
    try:
        t = yf.Ticker(yahoo_symbol(ticker))
        p = getattr(t.fast_info, "last_price", None)
        if p and p > 0:
            return round(float(p), 2)
        for k in ("regularMarketPrice", "currentPrice"):
            v = (t.info or {}).get(k)
            if v and float(v) > 0:
                return round(float(v), 2)
    except Exception:
        pass
    return None


def apply_trigger(live: float, eod: float, r1: float | None, r3: float | None) -> tuple[float, str]:
    raw = round(live, 2) if r1 is not None and r3 is not None and r1 >= r3 else round(live * 0.998, 2)
    floor = round(eod - SAFETY_BELOW_LAST_EOD, 2)
    min_t = round(floor + SAFETY_TICK_ABOVE_FLOOR, 2)
    trig = round(max(raw, min_t), 2)
    note = PASS_NOTE
    if trig > raw:
        note = f"{PASS_NOTE}; trigger raised to app safety (> {floor})"
    return trig, note


def position_size(trigger_eur: float, eurusd: float) -> tuple[float, float]:
    """Fractional shares: deploy full $50 budget (trigger converted EUR → USD)."""
    trigger_usd = eur_to_usd(trigger_eur, eurusd)
    qty = round(TRADE_SIZE_USD / trigger_usd, FRACTIONAL_QTY_DECIMALS)
    amount_usd = round(qty * trigger_usd, 2)
    return qty, amount_usd


def analyze_stock(ticker: str, bench_3m: float | None, eurusd: float) -> StockPick | None:
    df = fetch_history(ticker)
    if df is None:
        return None

    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    eod_eur = round(float(c.iloc[-1]), 2)
    live_eur = live_price(ticker) or eod_eur
    today = datetime.now(CET).strftime("%Y-%m-%d")

    r1, r3, r6, r12 = ret_pct(c, MOM_1M), ret_pct(c, MOM_3M), ret_pct(c, MOM_6M), ret_pct(c, MOM_12M)
    hi55 = float(h.iloc[-(TURTLE_ENTRY_DAYS + 1):-1].max())
    lo20 = float(l.iloc[-(TURTLE_EXIT_DAYS + 1):-1].min())

    breakout = live_eur >= hi55
    above_exit = live_eur > lo20
    rs = round(r3 - bench_3m, 2) if r3 is not None and bench_3m is not None else None
    rsi_v = rsi14(c)
    avg_v = float(v.iloc[-21:-1].mean()) if len(v) > 21 else 0
    vol_ok = avg_v > 0 and float(v.iloc[-1]) / avg_v >= VOL_MIN_FACTOR

    if not (
        breakout
        and above_exit
        and r12 is not None
        and r12 > 0
        and rs is not None
        and rs > 0
        and rsi_v is not None
        and RSI_MIN <= rsi_v <= RSI_MAX
        and vol_ok
    ):
        return None

    trig_eur, note = apply_trigger(live_eur, eod_eur, r1, r3)
    qty, amount_usd = position_size(trig_eur, eurusd)
    score = round(r12 * 0.4 + (r6 or 0) * 0.3 + (r3 or 0) * 0.2 + (r1 or 0) * 0.1, 2)
    trig_usd = eur_to_usd(trig_eur, eurusd)
    target_usd = round(trig_usd * (1 + PROFIT_TARGET_PCT / 100), 2)
    return StockPick(
        ticker,
        eur_to_usd(live_eur, eurusd),
        today,
        eur_to_usd(eod_eur, eurusd),
        trig_usd,
        target_usd,
        qty,
        amount_usd,
        note,
        score,
    )


def write_csv(path: Path, picks: list[StockPick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if picks:
        rows = [
            {
                "ticker": p.ticker,
                "todays_last_price_inr": p.price,
                "price_as_of": p.price_as_of,
                "last_eod_close_inr": p.last_eod,
                "tomorrow_buy_trigger_inr": p.trigger,
                "profit_target_inr": p.target,
                "qty": p.qty,
                "amount_inr": p.amount,
                "note": p.note,
            }
            for p in picks
        ]
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame([{c: "" for c in OUTPUT_COLUMNS}])
        df.loc[0, "note"] = NO_PICKS_NOTE
    df[OUTPUT_COLUMNS].to_csv(path, index=False)
    print(f"Wrote {path} ({len(df)} row(s))")


def cleanup_other_csvs(out_dir: Path, keep: Path) -> None:
    for f in out_dir.glob("*.csv"):
        if f.resolve() != keep.resolve():
            f.unlink()


def main() -> int:
    root = Path(__file__).resolve().parent
    out_dir = root / "output"
    run_date = datetime.now(CET).strftime("%Y%m%d")
    final_path = out_dir / f"final_output_{run_date}.csv"

    eurusd = fetch_eurusd()
    if eurusd is None:
        print("ERROR: Could not fetch EUR/USD rate.", file=sys.stderr)
        return 1

    print(
        f"German Stock Turtle + Dual Momentum | {len(GERMAN_STOCK_TICKERS)} stocks | "
        f"budget ${BUDGET_USD} (one-time) | +{PROFIT_TARGET_PCT}%"
    )
    print(f"Benchmark RS: {BENCHMARK} | EUR/USD: {eurusd} | Run: {datetime.now(CET).strftime('%Y-%m-%d %H:%M CET')}\n")

    bdf = fetch_history(BENCHMARK)
    bench_3m = ret_pct(bdf["Close"], MOM_3M) if bdf is not None else None
    if bench_3m is not None:
        print(f"{BENCHMARK} 3M return: {bench_3m}%\n")

    picks: list[StockPick] = []
    for i, ticker in enumerate(GERMAN_STOCK_TICKERS, 1):
        print(f"[{i}/{len(GERMAN_STOCK_TICKERS)}] {ticker}…", end=" ", flush=True)
        p = analyze_stock(ticker, bench_3m, eurusd)
        print("PASS" if p else "skip")
        if p:
            picks.append(p)

    picks.sort(key=lambda x: x.score, reverse=True)

    print("\n--- Tomorrow orders (Turtle + Dual Momentum) ---")
    if picks:
        for p in picks:
            print(
                f"  {p.ticker}: ${p.price} → LIMIT ${p.trigger} | target ${p.target} | "
                f"qty {p.qty} | ${p.amount} | score {p.score}"
            )
        print(f"  Picks: {len(picks)} | ${TRADE_SIZE_USD} fractional per row")
    else:
        print(f"  {NO_PICKS_NOTE}")

    write_csv(final_path, picks)
    cleanup_other_csvs(out_dir, final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
