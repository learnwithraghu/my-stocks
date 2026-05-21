#!/usr/bin/env python3
"""
Turtle + Dual Momentum screener — any index/universe via yfinance.
Output: output/final_output_YYYYMMDD.csv (passing symbols only).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

# ─── EDIT FOR YOUR INDEX / MARKET ─────────────────────────────
CONFIG = {
    "universe": [
        "NIFTYBEES", "GOLDBEES", "SILVERBEES", "BANKBEES", "ITBEES",
    ],
    "benchmark": "NIFTYBEES",
    "yahoo_suffix": ".NS",
    "budget": 300_000,
    "trade_size": 15_000,
    "profit_target_pct": 3.14,
    "max_picks": 20,
    "timezone": "Asia/Kolkata",
    "safety_below_eod": 0.06,
    "safety_tick_above": 0.01,
}

TURTLE_ENTRY_DAYS = 55
TURTLE_EXIT_DAYS = 20
MOM_1M, MOM_3M, MOM_6M, MOM_12M = 21, 63, 126, 252
MIN_HISTORY = MOM_12M + 10
RSI_MIN, RSI_MAX = 40, 80
VOL_MIN_FACTOR = 0.70
PASS_NOTE = "Passes all recommendation gates"

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
class Pick:
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


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}{CONFIG['yahoo_suffix']}"


def tz() -> ZoneInfo:
    return ZoneInfo(CONFIG["timezone"])


def fetch_history(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(yahoo_symbol(ticker), period="2y", interval="1d", progress=False, auto_adjust=True)
    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"]) if len(df.dropna(subset=["Close"])) >= 10 else None


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


def final_trigger(live: float, eod: float, r1: float | None, r3: float | None) -> tuple[float, str]:
    raw = round(live, 2) if r1 is not None and r3 is not None and r1 >= r3 else round(live * 0.998, 2)
    floor = round(eod - CONFIG["safety_below_eod"], 2)
    min_t = round(floor + CONFIG["safety_tick_above"], 2)
    trig = round(max(raw, min_t), 2)
    note = PASS_NOTE
    if trig > raw:
        note = f"{PASS_NOTE}; trigger raised to app safety (> {floor})"
    return trig, note


def analyze_symbol(ticker: str, bench_3m: float | None) -> Pick | None:
    df = fetch_history(ticker)
    if df is None:
        return None
    c = df["Close"]
    eod = round(float(c.iloc[-1]), 2)
    live = live_price(ticker) or eod
    today = datetime.now(tz()).strftime("%Y-%m-%d")

    h, l, v = df["High"], df["Low"], df["Volume"]
    if len(c) < MIN_HISTORY:
        return None

    r1, r3, r6, r12 = ret_pct(c, MOM_1M), ret_pct(c, MOM_3M), ret_pct(c, MOM_6M), ret_pct(c, MOM_12M)
    hi55 = float(h.iloc[-(TURTLE_ENTRY_DAYS + 1):-1].max())
    lo20 = float(l.iloc[-(TURTLE_EXIT_DAYS + 1):-1].min())

    breakout = live >= hi55
    above_exit = live > lo20
    rs = round(r3 - bench_3m, 2) if r3 is not None and bench_3m is not None else None
    rsi_v = rsi14(c)
    avg_v = float(v.iloc[-21:-1].mean()) if len(v) > 21 else 0
    vol_ok = avg_v > 0 and float(v.iloc[-1]) / avg_v >= VOL_MIN_FACTOR

    if not (breakout and above_exit and r12 and r12 > 0 and rs and rs > 0 and rsi_v and RSI_MIN <= rsi_v <= RSI_MAX and vol_ok):
        return None

    score = round(r12 * 0.4 + (r6 or 0) * 0.3 + (r3 or 0) * 0.2 + (r1 or 0) * 0.1, 2)
    trig, note = final_trigger(live, eod, r1, r3)
    target = round(trig * (1 + CONFIG["profit_target_pct"] / 100), 2)
    qty = max(1, int(CONFIG["trade_size"] // trig))
    amount = int(round(qty * trig))

    return Pick(ticker, live, today, eod, trig, target, qty, amount, note, score)


def write_csv(path: Path, picks: list[Pick]) -> None:
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
        df.loc[0, "note"] = "No ETFs to recommend at this time"
    df[OUTPUT_COLUMNS].to_csv(path, index=False)
    print(f"Wrote {path} ({len(df)} row(s))")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out = root / "output"
    out.mkdir(exist_ok=True)
    run_date = datetime.now(tz()).strftime("%Y%m%d")
    final = out / f"final_output_{run_date}.csv"

    bench = CONFIG["benchmark"]
    bdf = fetch_history(bench)
    bench_3m = ret_pct(bdf["Close"], MOM_3M) if bdf is not None else None
    print(f"Turtle + Dual Momentum | benchmark {bench} 3M={bench_3m}%")

    picks: list[Pick] = []
    for t in CONFIG["universe"]:
        print(f"  {t}…", end=" ", flush=True)
        p = analyze_symbol(t, bench_3m)
        print("PASS" if p else "skip")
        if p:
            picks.append(p)

    picks.sort(key=lambda x: x.score, reverse=True)
    max_n = min(CONFIG["max_picks"], CONFIG["budget"] // CONFIG["trade_size"])
    picks = picks[:max_n]

    write_csv(final, picks)
    for f in out.glob("*.csv"):
        if f.resolve() != final.resolve():
            f.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
