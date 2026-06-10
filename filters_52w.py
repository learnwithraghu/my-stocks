"""Shared 52-week high sweet-spot filters for Indian screeners."""

from __future__ import annotations

import pandas as pd

TRADING_DAYS_2W = 10
TRADING_DAYS_52W = 252
HIGH_TOLERANCE = 0.999

# Method-tuned bands: min/max % below 52-week high.
# Individual stocks (Piotroski, PEAD): avoid fresh highs while keeping momentum nearby.
BAND_STOCK = (5.0, 10.0)
# EGA: tight band — proximity is the primary signal (2-3 week horizon).
BAND_EGA = (5.0, 10.0)
# Turtle + Dual Momentum: slightly wider — trend already confirmed by breakout gates.
BAND_TURTLE_DM = (4.0, 12.0)


def above_200dma(hist: pd.DataFrame, price: float | None = None) -> bool | None:
    """True when price is above the 200-day moving average; None if history is insufficient."""
    if hist is None or hist.empty or len(hist) < 200:
        return None
    sma200 = float(hist["Close"].rolling(200).mean().iloc[-1])
    current = price if price is not None else float(hist["Close"].iloc[-1])
    return bool(current > sma200)


def gap_to_52w_high_pct(high_52w: float, current_price: float) -> float:
    if high_52w <= 0:
        return 100.0
    return round((high_52w - current_price) / high_52w * 100, 2)


def days_since_52w_high(highs: pd.Series, high_52w: float) -> int:
    """Trading days since the 52-week high was last reached."""
    arr = highs.values
    n = len(arr)
    lookback = min(TRADING_DAYS_52W, n)
    window_start = n - lookback
    last_idx = None
    for i in range(n - 1, window_start - 1, -1):
        if arr[i] >= high_52w * HIGH_TOLERANCE:
            last_idx = i
            break
    if last_idx is None:
        return lookback
    return (n - 1) - last_idx


def high_52w_from_history(hist: pd.DataFrame) -> float | None:
    if hist is None or hist.empty or "High" not in hist.columns:
        return None
    lookback = min(TRADING_DAYS_52W, len(hist))
    return float(hist["High"].iloc[-lookback:].max())


def passes_52w_sweet_spot(
    hist: pd.DataFrame,
    current_price: float,
    min_gap_pct: float,
    max_gap_pct: float,
    exclude_recent_high_days: int = TRADING_DAYS_2W,
) -> tuple[bool, float, str]:
    """Returns (passes, gap_pct, reject_reason)."""
    high_52w = high_52w_from_history(hist)
    if high_52w is None or current_price <= 0 or high_52w <= 0:
        return False, 0.0, "no history"

    gap_pct = gap_to_52w_high_pct(high_52w, current_price)

    if current_price > high_52w * HIGH_TOLERANCE:
        return False, gap_pct, "above 52w high"

    if gap_pct < min_gap_pct:
        return False, gap_pct, f"too close (<{min_gap_pct}%)"

    if gap_pct > max_gap_pct:
        return False, gap_pct, f"too far (>{max_gap_pct}%)"

    lookback = min(TRADING_DAYS_52W, len(hist))
    days_since = days_since_52w_high(hist["High"].iloc[-lookback:], high_52w)
    if days_since < exclude_recent_high_days:
        return False, gap_pct, f"52w high set {days_since}d ago"

    return True, gap_pct, "ok"
