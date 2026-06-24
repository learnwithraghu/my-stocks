#!/usr/bin/env python3
"""
Nifty Smallcap Box Breakout Screener
-------------------------------------
Stage 1 (traditional) : 30-day box formation + fresh breakout today
Stage 2 (modern)      : ADX trend emergence + volume spike (Man AHL / Winton)
Stage 3 (rank)        : box_score composite -> 1 winner

Investment: Rs 15,000 per winner (whole shares)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from smallcap_universe import NIFTY_SMALLCAP100_TICKERS

IST = ZoneInfo("Asia/Kolkata")
INVESTMENT_INR = 15_000
PROFIT_TARGET_PCT = 3.14
PROFIT_TARGET_GAIN_INR = 500
BOX_LOOKBACK_DAYS = 30
MIN_DAYS_IN_BOX = 15
BOX_WIDTH_MIN_PCT = 8.0
BOX_WIDTH_MAX_PCT = 22.0
MAX_BREAKOUT_PCT = 8.0
FRESH_BREAKOUT_DAYS = 5
MIN_VOLUME_SPIKE = 2.0
ADX_PERIOD = 14
ADX_BOX_MAX = 25.0
ADX_RISING_LOOKBACK = 5
MAX_MARKET_CAP_CR = 5000
MIN_HISTORY = BOX_LOOKBACK_DAYS + ADX_PERIOD + ADX_RISING_LOOKBACK + 5
TOP_N = 1

OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "company_name",
    "current_price_inr",
    "quantity",
    "investment_inr",
    "box_top_inr",
    "box_bottom_inr",
    "box_width_pct",
    "box_days",
    "breakout_pct",
    "volume_spike_ratio",
    "adx_14",
    "box_score",
    "entry_trigger_inr",
    "profit_target_inr",
    "stop_loss_inr",
    "market_cap_cr",
    "note",
]


@dataclass
class BoxMetrics:
    box_top_inr: float
    box_bottom_inr: float
    box_width_pct: float
    box_days: int
    breakout_pct: float
    volume_spike_ratio: float
    adx_14: float
    avg_box_adx: float


@dataclass
class StockResult:
    ticker: str
    company_name: str
    current_price_inr: float
    quantity: int
    investment_inr: float
    box_top_inr: float
    box_bottom_inr: float
    box_width_pct: float
    box_days: int
    breakout_pct: float
    volume_spike_ratio: float
    adx_14: float
    box_score: float
    entry_trigger_inr: float
    profit_target_inr: float
    stop_loss_inr: float
    market_cap_cr: Optional[float]
    note: str


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def profit_target_price(entry_price: float, quantity: int) -> float:
    pct_target = entry_price * (1 + PROFIT_TARGET_PCT / 100)
    fixed_gain_target = entry_price + (PROFIT_TARGET_GAIN_INR / max(quantity, 1))
    return round(min(pct_target, fixed_gain_target), 2)


def safe_get(info: dict, keys: list[str], default=None):
    for k in keys:
        if k in info and info[k] is not None:
            return info[k]
    return default


def fetch_price_history(ticker: str) -> Optional[pd.DataFrame]:
    try:
        hist = yf.Ticker(yahoo_symbol(ticker)).history(period="15mo")
        return hist if (not hist.empty and len(hist) >= MIN_HISTORY) else None
    except Exception:
        return None


def live_price(ticker: str) -> Optional[float]:
    try:
        info = yf.Ticker(yahoo_symbol(ticker)).info or {}
        p = safe_get(info, ["regularMarketPrice", "currentPrice", "previousClose"])
        return round(float(p), 2) if p and float(p) > 0 else None
    except Exception:
        return None


def compute_adx(hist: pd.DataFrame, period: int = ADX_PERIOD) -> pd.DataFrame:
    """Wilder ADX with +DI, -DI columns."""
    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    alpha = 1 / period
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr)

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace([float("inf"), -float("inf")], 0)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()

    return pd.DataFrame({"adx": adx, "plus_di": plus_di, "minus_di": minus_di})


def measure_box(hist: pd.DataFrame) -> Optional[BoxMetrics]:
    """Box on prior BOX_LOOKBACK_DAYS excluding today."""
    if len(hist) < BOX_LOOKBACK_DAYS + 1:
        return None

    box_slice = hist.iloc[-(BOX_LOOKBACK_DAYS + 1):-1]
    box_top = float(box_slice["High"].max())
    box_bottom = float(box_slice["Low"].min())
    if box_top <= box_bottom or box_bottom <= 0:
        return None

    midpoint = (box_top + box_bottom) / 2
    box_width_pct = round((box_top - box_bottom) / midpoint * 100, 2)

    closes = box_slice["Close"]
    box_days = int(((closes >= box_bottom) & (closes <= box_top)).sum())

    eod = float(hist["Close"].iloc[-1])
    breakout_pct = round((eod - box_top) / box_top * 100, 2) if box_top > 0 else 0.0

    vol_today = float(hist["Volume"].iloc[-1])
    vol_20d = float(hist["Volume"].iloc[-21:-1].mean()) if len(hist) >= 21 else 0.0
    volume_spike_ratio = round(vol_today / vol_20d, 2) if vol_20d > 0 else 0.0

    adx_df = compute_adx(hist)
    adx_14 = float(adx_df["adx"].iloc[-1])
    avg_box_adx = float(adx_df["adx"].iloc[-(BOX_LOOKBACK_DAYS + 1):-1].mean())

    return BoxMetrics(
        box_top_inr=round(box_top, 2),
        box_bottom_inr=round(box_bottom, 2),
        box_width_pct=box_width_pct,
        box_days=box_days,
        breakout_pct=breakout_pct,
        volume_spike_ratio=volume_spike_ratio,
        adx_14=round(adx_14, 2),
        avg_box_adx=round(avg_box_adx, 2),
    )


def passes_stage1(
    hist: pd.DataFrame, price: float, market_cap_cr: Optional[float]
) -> tuple[bool, str, Optional[BoxMetrics]]:
    if market_cap_cr is None or market_cap_cr >= MAX_MARKET_CAP_CR:
        return False, "market cap", None

    metrics = measure_box(hist)
    if metrics is None:
        return False, "no box", None

    if not (BOX_WIDTH_MIN_PCT <= metrics.box_width_pct <= BOX_WIDTH_MAX_PCT):
        return False, "box width", metrics

    if metrics.box_days < MIN_DAYS_IN_BOX:
        return False, "box days", metrics

    if price <= metrics.box_top_inr:
        return False, "no breakout", metrics

    if metrics.breakout_pct > MAX_BREAKOUT_PCT:
        return False, "late breakout", metrics

    recent_closes = hist["Close"].iloc[-(FRESH_BREAKOUT_DAYS + 1):-1]
    if (recent_closes > metrics.box_top_inr).any():
        return False, "stale breakout", metrics

    return True, "ok", metrics


def passes_stage2(hist: pd.DataFrame, metrics: BoxMetrics) -> tuple[bool, str]:
    adx_df = compute_adx(hist)
    plus_di = float(adx_df["plus_di"].iloc[-1])
    minus_di = float(adx_df["minus_di"].iloc[-1])
    adx_now = float(adx_df["adx"].iloc[-1])
    adx_prior = float(adx_df["adx"].iloc[-(ADX_RISING_LOOKBACK + 1)])

    if metrics.avg_box_adx >= ADX_BOX_MAX:
        return False, "adx not consolidating"

    if plus_di <= minus_di:
        return False, "bearish di"

    if adx_now <= adx_prior:
        return False, "adx flat"

    if metrics.volume_spike_ratio < MIN_VOLUME_SPIKE:
        return False, "low volume"

    return True, "ok"


def box_score(metrics: BoxMetrics) -> float:
    width_component = (BOX_WIDTH_MAX_PCT - metrics.box_width_pct) / (
        BOX_WIDTH_MAX_PCT - BOX_WIDTH_MIN_PCT
    )
    breakout_component = min(metrics.breakout_pct, MAX_BREAKOUT_PCT) / MAX_BREAKOUT_PCT
    return round(
        0.45 * metrics.volume_spike_ratio
        + 0.30 * width_component
        + 0.25 * breakout_component,
        4,
    )


def analyze_stock(ticker: str, hist: pd.DataFrame) -> Optional[StockResult]:
    try:
        sym = yahoo_symbol(ticker)
        stock = yf.Ticker(sym)
        info = stock.info or {}

        market_cap = safe_get(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None

        eod = round(float(hist["Close"].iloc[-1]), 2)
        price = live_price(ticker) or eod

        ok1, reason1, metrics = passes_stage1(hist, price, market_cap_cr)
        if not ok1 or metrics is None:
            return None

        ok2, reason2 = passes_stage2(hist, metrics)
        if not ok2:
            return None

        score = box_score(metrics)
        company_name = safe_get(info, ["longName", "shortName"], ticker) or ticker
        quantity = max(1, int(INVESTMENT_INR // price))
        investment = round(quantity * price, 2)
        entry = price
        profit_target = profit_target_price(entry, quantity)
        stop_loss = metrics.box_bottom_inr

        note = (
            f"Box:{metrics.box_width_pct:.1f}%w {metrics.box_days}d | "
            f"Breakout:+{metrics.breakout_pct:.1f}% | "
            f"Vol:{metrics.volume_spike_ratio:.1f}x | "
            f"ADX:{metrics.adx_14:.1f} (box avg {metrics.avg_box_adx:.1f}) | "
            f"score:{score:.2f}"
        )

        return StockResult(
            ticker=ticker,
            company_name=company_name,
            current_price_inr=round(price, 2),
            quantity=quantity,
            investment_inr=investment,
            box_top_inr=metrics.box_top_inr,
            box_bottom_inr=metrics.box_bottom_inr,
            box_width_pct=metrics.box_width_pct,
            box_days=metrics.box_days,
            breakout_pct=metrics.breakout_pct,
            volume_spike_ratio=metrics.volume_spike_ratio,
            adx_14=metrics.adx_14,
            box_score=score,
            entry_trigger_inr=round(entry, 2),
            profit_target_inr=profit_target,
            stop_loss_inr=stop_loss,
            market_cap_cr=market_cap_cr,
            note=note,
        )
    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None


def pick_winner(candidates: list[StockResult]) -> Optional[StockResult]:
    if not candidates:
        return None

    def sort_key(c: StockResult) -> tuple:
        cap = c.market_cap_cr if c.market_cap_cr is not None else 999999.0
        return (c.box_score, c.volume_spike_ratio, -cap)

    return max(candidates, key=sort_key)


def write_csv(path: Path, result: Optional[StockResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(IST).strftime("%Y-%m-%d")

    if result:
        row = asdict(result)
        row["date"] = today
        df = pd.DataFrame([row])
    else:
        df = pd.DataFrame([{c: "" for c in OUTPUT_COLUMNS}])
        df.loc[0, "date"] = today
        df.loc[0, "note"] = "No stocks to recommend at this time"

    df = df[OUTPUT_COLUMNS]
    df.to_csv(path, index=False)
    print(f"Wrote {path}")


def main() -> int:
    root = Path(__file__).resolve().parent
    csv_path = root / "output" / "box_winner.csv"
    today = datetime.now(IST).strftime("%Y-%m-%d")
    universe = NIFTY_SMALLCAP100_TICKERS

    print("Nifty Smallcap Box Breakout Screener")
    print(
        "Stage 1: Box formation + breakout  |  "
        "Stage 2: ADX + volume spike  |  Stage 3: box_score rank"
    )
    print(
        f"Investment: Rs{INVESTMENT_INR:,}  |  Target: min(Rs{PROFIT_TARGET_GAIN_INR}, +{PROFIT_TARGET_PCT}%)  |  "
        f"Universe: {len(universe)} stocks (cap < Rs{MAX_MARKET_CAP_CR:,} Cr)  |  Date: {today}\n"
    )

    print(f"── Stage 1: Box + breakout ({len(universe)} stocks) ──")
    stage1_survivors: list[tuple[str, pd.DataFrame]] = []

    for i, ticker in enumerate(universe, 1):
        print(f"  [{i:3d}/{len(universe)}] {ticker:<20}", end=" ", flush=True)
        hist = fetch_price_history(ticker)
        if hist is None:
            print("skip (no data)")
            continue

        sym = yahoo_symbol(ticker)
        info = yf.Ticker(sym).info or {}
        market_cap = safe_get(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None
        eod = round(float(hist["Close"].iloc[-1]), 2)
        price = live_price(ticker) or eod

        ok, reason, metrics = passes_stage1(hist, price, market_cap_cr)
        if ok and metrics:
            print(
                f"pass  box:{metrics.box_width_pct:.1f}%  "
                f"breakout:+{metrics.breakout_pct:.1f}%  cap:{market_cap_cr}Cr"
            )
            stage1_survivors.append((ticker, hist))
        else:
            print(f"fail ({reason})")

    print(f"\nStage 1: {len(universe)} -> {len(stage1_survivors)} stocks\n")

    print("── Stage 2: ADX trend emergence + volume spike ──")
    candidates: list[StockResult] = []

    for j, (ticker, hist) in enumerate(stage1_survivors, 1):
        print(f"  [{j:3d}/{len(stage1_survivors)}] {ticker:<20}", end=" ", flush=True)
        metrics = measure_box(hist)
        if metrics is None:
            print("fail (metrics)")
            continue
        ok2, reason2 = passes_stage2(hist, metrics)
        if not ok2:
            print(f"fail ({reason2})")
            continue

        result = analyze_stock(ticker, hist)
        if result:
            print(f"pass  score:{result.box_score:.2f}  vol:{result.volume_spike_ratio:.1f}x")
            candidates.append(result)
        else:
            print("fail (analyze)")

    print(f"\nStage 2: {len(stage1_survivors)} -> {len(candidates)} candidates\n")

    winner = pick_winner(candidates)

    print("=" * 60)
    print("STAGE SUMMARY")
    print(f"  Stage 1 (box)      : {len(universe)} -> {len(stage1_survivors)}")
    print(f"  Stage 2 (ADX+vol)  : {len(stage1_survivors)} -> {len(candidates)}")
    print(f"  Stage 3 (1 winner) : {len(candidates)} -> {1 if winner else 0}")
    print("=" * 60)

    print("\nBOX BREAKOUT WINNER")
    print("=" * 60)
    if winner:
        print(f"Stock     : {winner.ticker} ({winner.company_name})")
        print(f"Price     : Rs{winner.current_price_inr}")
        print(
            f"Box       : Rs{winner.box_bottom_inr} - Rs{winner.box_top_inr} "
            f"({winner.box_width_pct:.1f}% wide, {winner.box_days}d inside)"
        )
        print(
            f"Breakout  : +{winner.breakout_pct:.1f}%  |  Vol spike: {winner.volume_spike_ratio:.1f}x  |  "
            f"ADX: {winner.adx_14:.1f}"
        )
        print(f"Entry     : Rs{winner.entry_trigger_inr}  |  Target: Rs{winner.profit_target_inr}")
        print(f"Stop      : Rs{winner.stop_loss_inr} (box bottom)")
        print(f"Quantity  : {winner.quantity} shares  |  Amount: Rs{winner.investment_inr}")
        print(f"Score     : {winner.box_score:.2f}")
        print(f"Mkt Cap   : Rs{winner.market_cap_cr} Cr" if winner.market_cap_cr else "Mkt Cap   : N/A")
        print(f"Criteria  : {winner.note}")
    else:
        print("No winner — no stocks passed all three stages.")

    print("=" * 60)
    write_csv(csv_path, winner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
