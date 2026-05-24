#!/usr/bin/env python3
"""
US stock screener — Tight Consolidation Breakout (TCB).

Method  : Stock consolidates in a tight range (<8% spread, 15 days),
          then breaks above the range with 2x+ normal volume.
          Post-breakout extension typically 15-25% in 5-10 trading days.

Budget  : $20 USD per trade (fractional shares)
Fee     : $1 per buy → need $24 exit on $20 to net $3 profit → 20% target
Picks   : Top 2 by breakout score each day
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from us_universe import US_STOCK_TICKERS

ET = ZoneInfo("America/New_York")

TRADE_SIZE_USD          = 20
PROFIT_TARGET_PCT       = 20.0      # need 20% gain to net $3 after $1 fee on $20 invest
FRACTIONAL_QTY_DECIMALS = 6
MAX_PICKS               = 2

CONSOLIDATION_DAYS      = 15        # days to look back for the tight range
CONSOLIDATION_RANGE_PCT = 0.12      # max spread: 12% (large caps swing wider than small caps)
BREAKOUT_VOL_FACTOR     = 1.3       # breakout day volume must be 1.3x 20-day avg (large cap norm)
VOL_LOOKBACK            = 20        # days for average volume baseline
HISTORY_PERIOD          = "6mo"
MIN_HISTORY             = CONSOLIDATION_DAYS + VOL_LOOKBACK + 10

SAFETY_BELOW_LAST_EOD   = 0.01
SAFETY_TICK_ABOVE_FLOOR = 0.01

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
    return ticker


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


def position_size(trigger: float) -> tuple[float, float]:
    qty = round(TRADE_SIZE_USD / trigger, FRACTIONAL_QTY_DECIMALS)
    amount = round(qty * trigger, 2)
    return qty, amount


def analyze_stock(ticker: str) -> StockPick | None:
    df = fetch_history(ticker)
    if df is None:
        return None

    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

    # ── Consolidation window: 15 bars ending yesterday (exclude today) ───────
    consol_h = h.iloc[-(CONSOLIDATION_DAYS + 1):-1]
    consol_l = l.iloc[-(CONSOLIDATION_DAYS + 1):-1]
    range_high = float(consol_h.max())
    range_low  = float(consol_l.min())

    if range_low <= 0:
        return None

    range_pct = (range_high - range_low) / range_low
    if range_pct > CONSOLIDATION_RANGE_PCT:
        return None  # range too wide — not a tight consolidation

    # ── Breakout: today's price must clear the consolidation high ────────────
    eod  = round(float(c.iloc[-1]), 2)
    live = live_price(ticker) or eod

    if live <= range_high:
        return None  # not broken out yet

    # ── Volume surge on breakout day: 2x+ 20-day average ────────────────────
    avg_vol  = float(v.iloc[-(VOL_LOOKBACK + 1):-1].mean())
    today_vol = float(v.iloc[-1])
    vol_ratio = today_vol / avg_vol if avg_vol > 0 else 0.0

    if vol_ratio < BREAKOUT_VOL_FACTOR:
        return None  # breakout not confirmed by volume

    # ── Entry trigger (enter at breakout price, apply safety floor) ──────────
    floor = round(eod - SAFETY_BELOW_LAST_EOD, 2)
    trig  = round(max(live, floor + SAFETY_TICK_ABOVE_FLOOR), 2)
    target = round(trig * (1 + PROFIT_TARGET_PCT / 100), 2)
    qty, amount = position_size(trig)

    # ── Score: breakout strength × volume surge ───────────────────────────────
    breakout_pct = (live - range_high) / range_high * 100
    score = round(breakout_pct * vol_ratio, 4)

    today = datetime.now(ET).strftime("%Y-%m-%d")
    note = (
        f"TCB: range {range_pct*100:.1f}% over {CONSOLIDATION_DAYS}d | "
        f"breakout +{breakout_pct:.1f}% above range | "
        f"vol {vol_ratio:.1f}x avg | score {score:.2f}"
    )

    return StockPick(ticker, live, today, eod, trig, target, qty, amount, note, score)


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
    run_date = datetime.now(ET).strftime("%Y%m%d")
    final_path = out_dir / f"final_output_{run_date}.csv"

    print("US Stock Tight Consolidation Breakout (TCB) Screener")
    print(
        f"Universe: {len(US_STOCK_TICKERS)} stocks | "
        f"${TRADE_SIZE_USD}/trade | target +{PROFIT_TARGET_PCT}% (~${TRADE_SIZE_USD * PROFIT_TARGET_PCT/100 - 1:.0f} net) | "
        f"top {MAX_PICKS} picks"
    )
    print(f"Consolidation: {CONSOLIDATION_DAYS}d tight range <{CONSOLIDATION_RANGE_PCT*100:.0f}% | "
          f"Vol surge: {BREAKOUT_VOL_FACTOR}x | Run: {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}\n")

    all_picks: list[StockPick] = []
    for i, ticker in enumerate(US_STOCK_TICKERS, 1):
        print(f"[{i}/{len(US_STOCK_TICKERS)}] {ticker}…", end=" ", flush=True)
        p = analyze_stock(ticker)
        if p:
            parts = p.note.split("|")
            print(f"PASS  score:{p.score:.2f}  {parts[1].strip()}  {parts[2].strip()}")
            all_picks.append(p)
        else:
            print("skip")

    all_picks.sort(key=lambda x: x.score, reverse=True)
    winners = all_picks[:MAX_PICKS]

    print(f"\n--- TCB picks (top {MAX_PICKS} of {len(all_picks)} candidates) ---")
    if winners:
        for rank, p in enumerate(winners, 1):
            print(
                f"  #{rank} {p.ticker}: ${p.price} → LIMIT ${p.trigger} | "
                f"target ${p.target} (+{PROFIT_TARGET_PCT}%) | "
                f"qty {p.qty} | ${p.amount} | score {p.score}"
            )
        print(f"\n  Net profit if target hit: ~${TRADE_SIZE_USD * PROFIT_TARGET_PCT/100 - 1:.0f} per trade after $1 fee")
    else:
        print(f"  {NO_PICKS_NOTE}")

    write_csv(final_path, winners)
    cleanup_other_csvs(out_dir, final_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
