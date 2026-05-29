#!/usr/bin/env python3
"""
Nifty 100 stock screener — Turtle trading + Dual Momentum (.agent/turtle-dual-momentum).
Output: output/final_output_YYYYMMDD.csv (passing stocks only).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from nifty100_universe import NIFTY100_TICKERS

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from filters_52w import BAND_TURTLE_DM, passes_52w_sweet_spot

IST = ZoneInfo("Asia/Kolkata")
BENCHMARK = "NIFTYBEES"
BUDGET_INR = 300_000
TRADE_SIZE_INR = 10_000
MAX_SLOTS = 2
PROFIT_TARGET_PCT = 3.14
PROFIT_TARGET_GAIN_INR = 500

TURTLE_ENTRY_DAYS = 55
TURTLE_EXIT_DAYS = 20
MOM_1M, MOM_3M, MOM_6M, MOM_12M = 21, 63, 126, 252
MIN_HISTORY = MOM_12M + 10
HISTORY_PERIOD = "2y"
RSI_MIN, RSI_MAX = 40, 80
VOL_MIN_FACTOR = 0.70
SAFETY_BELOW_LAST_EOD_INR = 0.06
SAFETY_TICK_ABOVE_FLOOR = 0.01
PASS_NOTE = "Passes all recommendation gates"
NO_PICKS_NOTE = "No stocks to recommend at this time"

OUTPUT_COLUMNS = [
    "ticker",
    "todays_last_price_inr",
    "price_as_of",
    "last_eod_close_inr",
    "gap_to_52wh_pct",
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
    qty: int
    amount: int
    note: str
    score: float
    gap_to_52wh_pct: float


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


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
    floor = round(eod - SAFETY_BELOW_LAST_EOD_INR, 2)
    min_t = round(floor + SAFETY_TICK_ABOVE_FLOOR, 2)
    trig = round(max(raw, min_t), 2)
    note = PASS_NOTE
    if trig > raw:
        note = f"{PASS_NOTE}; trigger raised to app safety (> {floor})"
    return trig, note


def position_size(trigger: float) -> tuple[int, int]:
    qty = max(1, int(TRADE_SIZE_INR // trigger))
    return qty, int(round(qty * trigger))


def profit_target_price(entry_price: float, qty: int) -> float:
    pct_target = entry_price * (1 + PROFIT_TARGET_PCT / 100)
    fixed_gain_target = entry_price + (PROFIT_TARGET_GAIN_INR / max(qty, 1))
    return round(min(pct_target, fixed_gain_target), 2)


def analyze_stock(ticker: str, bench_3m: float | None) -> StockPick | None:
    df = fetch_history(ticker)
    if df is None:
        return None

    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    eod = round(float(c.iloc[-1]), 2)
    live = live_price(ticker) or eod
    today = datetime.now(IST).strftime("%Y-%m-%d")

    r1, r3, r6, r12 = ret_pct(c, MOM_1M), ret_pct(c, MOM_3M), ret_pct(c, MOM_6M), ret_pct(c, MOM_12M)
    hi55 = float(h.iloc[-(TURTLE_ENTRY_DAYS + 1):-1].max())
    lo20 = float(l.iloc[-(TURTLE_EXIT_DAYS + 1):-1].min())

    breakout = live >= hi55
    above_exit = live > lo20
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

    passes_52w, gap_52wh, _ = passes_52w_sweet_spot(df, live, *BAND_TURTLE_DM)
    if not passes_52w:
        return None

    score = round(r12 * 0.4 + (r6 or 0) * 0.3 + (r3 or 0) * 0.2 + (r1 or 0) * 0.1, 2)
    trig, note = apply_trigger(live, eod, r1, r3)
    qty, amount = position_size(trig)
    target = profit_target_price(trig, qty)
    return StockPick(ticker, live, today, eod, trig, target, qty, amount, note, score, gap_52wh)


def write_csv(path: Path, picks: list[StockPick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if picks:
        rows = [
            {
                "ticker": p.ticker,
                "todays_last_price_inr": p.price,
                "price_as_of": p.price_as_of,
                "last_eod_close_inr": p.last_eod,
                "gap_to_52wh_pct": p.gap_to_52wh_pct,
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
    run_date = datetime.now(IST).strftime("%Y%m%d")
    final_path = out_dir / f"final_output_{run_date}.csv"

    print(
        f"Nifty 100 Turtle + Dual Momentum | {len(NIFTY100_TICKERS)} stocks | "
        f"budget ₹{BUDGET_INR:,} | ₹{TRADE_SIZE_INR:,}/trade | "
        f"target min(₹{PROFIT_TARGET_GAIN_INR}, +{PROFIT_TARGET_PCT}%)"
    )
    print(f"Benchmark RS: {BENCHMARK} | Run: {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}\n")

    bdf = fetch_history(BENCHMARK)
    bench_3m = ret_pct(bdf["Close"], MOM_3M) if bdf is not None else None
    if bench_3m is not None:
        print(f"{BENCHMARK} 3M return: {bench_3m}%\n")

    picks: list[StockPick] = []
    for i, ticker in enumerate(NIFTY100_TICKERS, 1):
        print(f"[{i}/{len(NIFTY100_TICKERS)}] {ticker}…", end=" ", flush=True)
        p = analyze_stock(ticker, bench_3m)
        print("PASS" if p else "skip")
        if p:
            picks.append(p)

    picks.sort(key=lambda x: x.score, reverse=True)
    picks = picks[:MAX_SLOTS]

    print("\n--- Tomorrow orders (Turtle + Dual Momentum) ---")
    if picks:
        for p in picks:
            print(
                f"  {p.ticker}: ₹{p.price} → LIMIT ₹{p.trigger} | target ₹{p.target} | "
                f"qty {p.qty} | ₹{p.amount} | score {p.score}"
            )
        deploy = sum(p.amount for p in picks)
        print(f"  Slots: {len(picks)}/{MAX_SLOTS} | Deploy ~₹{deploy:,}")
    else:
        print(f"  {NO_PICKS_NOTE}")

    write_csv(final_path, picks)
    cleanup_other_csvs(out_dir, final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
