#!/usr/bin/env python3
"""
Nifty Midcap + Smallcap EGA Screener
--------------------------------------
Method  : Earnings Growth Acceleration (EGA) + 52-Week High Proximity
Horizon : 2-3 weeks
Winners : Top 2 by EGA composite score
Budget  : Rs 5,000 per stock

Stage 1 (fast)   : Within 10% of 52-week high + positive 5-day momentum
Stage 2 (detail) : EGA quality gate (earnings growth >= 10%, revenue >= 5%)
                   + RSI(14) 50-78 + volume confirmation
Stage 3          : EGA composite score -> top 2 winners
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
import yfinance as yf

from midsmall_universe import MIDSMALL_TICKERS

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from filters_52w import BAND_EGA, high_52w_from_history, passes_52w_sweet_spot

IST = ZoneInfo("Asia/Kolkata")
INVESTMENT_INR = 5000
EGA_MIN_GAP_PCT, EGA_MAX_GAP_PCT = BAND_EGA
MIN_EARNINGS_GROWTH = 0.10  # 10% YoY earnings growth
MIN_REVENUE_GROWTH = 0.05   # 5% YoY revenue growth
RSI_MIN = 50
RSI_MAX = 78
MIN_VOLUME_RATIO = 0.80     # 5-day avg volume >= 80% of 20-day avg
TOP_N = 2

OUTPUT_COLUMNS = [
    "date", "ticker", "company_name", "current_price_inr",
    "quantity", "investment_inr",
    "earnings_growth_pct", "revenue_growth_pct",
    "gap_to_52wh_pct", "momentum_5d_pct", "rsi_14",
    "ega_score", "pe_ratio", "market_cap_cr", "note",
]


@dataclass
class StockResult:
    ticker: str
    company_name: str
    current_price_inr: float
    quantity: int
    investment_inr: float
    earnings_growth_pct: float
    revenue_growth_pct: float
    gap_to_52wh_pct: float
    momentum_5d_pct: float
    rsi_14: float
    ega_score: float
    pe_ratio: Optional[float]
    market_cap_cr: Optional[float]
    note: str


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def safe_get(info: dict, keys: list[str], default=None):
    for k in keys:
        if k in info and info[k] is not None:
            return info[k]
    return default


def df_row(df: pd.DataFrame, names: list[str]) -> Optional[pd.Series]:
    for name in names:
        if name in df.index:
            return df.loc[name]
    return None


def val(series: Optional[pd.Series], col: int) -> Optional[float]:
    if series is None:
        return None
    try:
        v = series.iloc[col]
        return None if pd.isna(v) else float(v)
    except (IndexError, TypeError):
        return None


def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    delta = prices.diff().dropna()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    last_loss = avg_loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = avg_gain.iloc[-1] / last_loss
    return round(100 - (100 / (1 + rs)), 2)


def passes_proximity_filter(
    info: dict, hist: pd.DataFrame
) -> tuple[bool, float, float]:
    """Returns (passes, gap_to_52wh_pct, momentum_5d_pct)."""
    current_price = safe_get(info, ["currentPrice", "regularMarketPrice", "previousClose"])
    if not current_price or current_price <= 0:
        return False, 0.0, 0.0

    if len(hist) < 6:
        return False, 0.0, 0.0

    passes_52w, gap_pct, _ = passes_52w_sweet_spot(hist, current_price, *BAND_EGA)
    momentum_5d = round((hist["Close"].iloc[-1] / hist["Close"].iloc[-6] - 1) * 100, 2)

    passes = passes_52w and (momentum_5d > 0)
    return passes, gap_pct, momentum_5d


def check_ega(
    info: dict, financials: Optional[pd.DataFrame]
) -> tuple[bool, float, float]:
    """
    Returns (passes, earnings_growth_pct, revenue_growth_pct).
    Uses quarterly YoY from info first; falls back to annual financials.
    """
    eq_growth = safe_get(info, ["earningsGrowth", "earningsQuarterlyGrowth"])
    rev_growth = safe_get(info, ["revenueGrowth"])

    earnings_growth: Optional[float] = float(eq_growth) if eq_growth is not None else None
    revenue_growth: Optional[float] = float(rev_growth) if rev_growth is not None else None

    # Fallback to annual financials for missing values
    if (earnings_growth is None or revenue_growth is None) and (
        financials is not None and not financials.empty and financials.shape[1] >= 2
    ):
        ni = df_row(financials, ["Net Income", "Net Income Common Stockholders"])
        rev = df_row(financials, ["Total Revenue", "Operating Revenue"])
        ni0, ni1 = val(ni, 0), val(ni, 1)
        rev0, rev1 = val(rev, 0), val(rev, 1)

        if earnings_growth is None and ni0 is not None and ni1 is not None and abs(ni1) > 0:
            earnings_growth = (ni0 - ni1) / abs(ni1)

        if revenue_growth is None and rev0 is not None and rev1 is not None and rev1 > 0:
            revenue_growth = (rev0 - rev1) / abs(rev1)

    if earnings_growth is None or revenue_growth is None:
        return False, 0.0, 0.0

    passes = (earnings_growth >= MIN_EARNINGS_GROWTH) and (revenue_growth >= MIN_REVENUE_GROWTH)
    return passes, round(earnings_growth * 100, 2), round(revenue_growth * 100, 2)


def calculate_ega_score(
    earnings_growth_pct: float,
    revenue_growth_pct: float,
    gap_pct: float,
    momentum_5d_pct: float,
) -> float:
    """
    Composite score tuned for 2-3 week trade horizon.
    Proximity and near-term momentum are weighted heavily.
    """
    # Proximity: 0 at max gap, 100 at min gap (sweet-spot band)
    band_width = EGA_MAX_GAP_PCT - EGA_MIN_GAP_PCT
    proximity_score = max(
        0.0,
        (EGA_MAX_GAP_PCT - gap_pct) / band_width * 100 if band_width > 0 else 0.0,
    )

    score = (
        0.30 * min(earnings_growth_pct, 100.0) +   # cap to avoid outlier distortion
        0.25 * min(revenue_growth_pct, 50.0) +
        0.25 * proximity_score +
        0.20 * min(max(momentum_5d_pct, 0.0), 20.0)
    )
    return round(score, 4)


def analyze_stock(
    ticker: str, hist: pd.DataFrame, info: dict
) -> Optional[StockResult]:
    """Stage 2: fetch financials, EGA gate, RSI, volume, composite score."""
    try:
        current_price = safe_get(info, ["currentPrice", "regularMarketPrice", "previousClose"])
        if not current_price or current_price <= 0:
            return None

        # RSI filter
        rsi = calculate_rsi(hist["Close"])
        if rsi is None or not (RSI_MIN <= rsi <= RSI_MAX):
            return None

        # Volume confirmation: 5-day avg >= MIN_VOLUME_RATIO × 20-day avg
        if len(hist) >= 20:
            vol_5d = hist["Volume"].iloc[-5:].mean()
            vol_20d = hist["Volume"].iloc[-20:].mean()
            if vol_20d > 0 and (vol_5d / vol_20d) < MIN_VOLUME_RATIO:
                return None

        # EGA quality gate (fetch annual financials as fallback)
        try:
            financials = yf.Ticker(yahoo_symbol(ticker)).financials
        except Exception:
            financials = None

        passes_ega, earnings_growth_pct, revenue_growth_pct = check_ega(info, financials)
        if not passes_ega:
            return None

        high_52w = safe_get(info, ["fiftyTwoWeekHigh"])
        if not high_52w or high_52w <= 0:
            high_52w = high_52w_from_history(hist)
        if not high_52w:
            return None
        gap_pct = round((high_52w - current_price) / high_52w * 100, 2)
        momentum_5d = round((hist["Close"].iloc[-1] / hist["Close"].iloc[-6] - 1) * 100, 2)

        ega_score = calculate_ega_score(
            earnings_growth_pct, revenue_growth_pct, gap_pct, momentum_5d
        )

        market_cap = safe_get(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None
        pe_ratio = safe_get(info, ["trailingPE", "forwardPE"])
        company_name = safe_get(info, ["longName", "shortName"], ticker)
        quantity = max(1, int(INVESTMENT_INR // current_price))
        investment = round(quantity * current_price, 2)

        note = (
            f"EarnGrowth:{earnings_growth_pct:+.1f}% "
            f"RevGrowth:{revenue_growth_pct:+.1f}% | "
            f"52wh_gap:{gap_pct:.1f}% "
            f"5dMom:{momentum_5d:+.1f}% "
            f"RSI:{rsi:.0f} | "
            f"EGAscore:{ega_score:.2f}"
        )

        return StockResult(
            ticker=ticker,
            company_name=company_name,
            current_price_inr=round(current_price, 2),
            quantity=quantity,
            investment_inr=investment,
            earnings_growth_pct=earnings_growth_pct,
            revenue_growth_pct=revenue_growth_pct,
            gap_to_52wh_pct=gap_pct,
            momentum_5d_pct=momentum_5d,
            rsi_14=rsi,
            ega_score=ega_score,
            pe_ratio=round(pe_ratio, 2) if pe_ratio else None,
            market_cap_cr=market_cap_cr,
            note=note,
        )

    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None


def write_csv(path: Path, results: list[StockResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(IST).strftime("%Y-%m-%d")

    if results:
        rows = []
        for r in results:
            row = asdict(r)
            row["date"] = today
            rows.append(row)
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame([{c: "" for c in OUTPUT_COLUMNS}])
        df.loc[0, "date"] = today
        df.loc[0, "note"] = "No stocks passed all stages"

    df = df[OUTPUT_COLUMNS]
    df.to_csv(path, index=False)
    print(f"Wrote {path}")


def main() -> int:
    root = Path(__file__).resolve().parent
    csv_path = root / "output" / "ega_winners.csv"
    today = datetime.now(IST).strftime("%Y-%m-%d")

    print("Nifty Midcap + Smallcap EGA Screener")
    print(f"Method  : Earnings Growth Acceleration + 52-Week High Proximity")
    print(f"Horizon : 2-3 weeks  |  Budget: Rs{INVESTMENT_INR:,}/stock  |  Winners: {TOP_N}")
    print(f"Universe: {len(MIDSMALL_TICKERS)} stocks  |  Date: {today}\n")

    # ── Stage 1: 52-week high proximity + 5-day momentum ────────────────────
    print(
        f"── Stage 1: {EGA_MIN_GAP_PCT:.0f}-{EGA_MAX_GAP_PCT:.0f}% below 52-week high "
        f"(no fresh high in 2w) + positive 5-day momentum ──"
    )
    stage1_survivors: list[tuple[str, pd.DataFrame, dict]] = []

    for i, ticker in enumerate(MIDSMALL_TICKERS, 1):
        print(f"  [{i:3d}/{len(MIDSMALL_TICKERS)}] {ticker:<20}", end=" ", flush=True)
        try:
            stock = yf.Ticker(yahoo_symbol(ticker))
            info = stock.info or {}
            if not info:
                print("skip (no info)")
                continue
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 20:
                print("skip (no history)")
                continue

            passes, gap_pct, mom_5d = passes_proximity_filter(info, hist)
            if passes:
                print(f"pass  gap:{gap_pct:.1f}%  5d:{mom_5d:+.1f}%")
                stage1_survivors.append((ticker, hist, info))
            else:
                print(f"fail  gap:{gap_pct:.1f}%  5d:{mom_5d:+.1f}%")
        except Exception as e:
            print(f"error ({e})")

    print(f"\nStage 1: {len(MIDSMALL_TICKERS)} -> {len(stage1_survivors)} stocks near 52-week high\n")

    # ── Stage 2: EGA quality gate + RSI + volume ────────────────────────────
    print(
        f"── Stage 2: EGA gate (EarnGrowth>={MIN_EARNINGS_GROWTH*100:.0f}%  "
        f"RevGrowth>={MIN_REVENUE_GROWTH*100:.0f}%)  "
        f"RSI {RSI_MIN}-{RSI_MAX}  Volume>={MIN_VOLUME_RATIO*100:.0f}% avg ──"
    )
    candidates: list[StockResult] = []

    for j, (ticker, hist, info) in enumerate(stage1_survivors, 1):
        print(f"  [{j:3d}/{len(stage1_survivors)}] {ticker:<20}", end=" ", flush=True)
        result = analyze_stock(ticker, hist, info)
        if result:
            print(f"pass  score:{result.ega_score:.2f}  EG:{result.earnings_growth_pct:+.1f}%  RG:{result.revenue_growth_pct:+.1f}%")
            candidates.append(result)
        else:
            print("fail (EGA/RSI/volume)")

    print(f"\nStage 2: {len(stage1_survivors)} -> {len(candidates)} EGA-qualified candidates\n")

    # ── Stage 3: Top 2 by EGA composite score ───────────────────────────────
    candidates.sort(key=lambda x: x.ega_score, reverse=True)
    winners = candidates[:TOP_N]

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 65)
    print("STAGE SUMMARY")
    print(f"  Stage 1 (52wh proximity) : {len(MIDSMALL_TICKERS)} -> {len(stage1_survivors)} stocks")
    print(f"  Stage 2 (EGA quality)    : {len(stage1_survivors)} -> {len(candidates)} stocks")
    print(f"  Stage 3 (top {TOP_N} by score) : {len(candidates)} -> {len(winners)} winners")
    print("=" * 65)

    if winners:
        for rank, w in enumerate(winners, 1):
            print(f"\nWINNER #{rank}")
            print("-" * 65)
            print(f"Stock      : {w.ticker} ({w.company_name})")
            print(f"Price      : Rs{w.current_price_inr}")
            print(f"EGA Score  : {w.ega_score:.2f}")
            print(f"EarnGrowth : {w.earnings_growth_pct:+.1f}%  RevGrowth: {w.revenue_growth_pct:+.1f}%")
            print(f"52wh Gap   : {w.gap_to_52wh_pct:.1f}% below 52-week high")
            print(f"5-Day Mom  : {w.momentum_5d_pct:+.1f}%")
            print(f"RSI(14)    : {w.rsi_14:.1f}")
            print(f"Quantity   : {w.quantity} shares")
            print(f"Amount     : Rs{w.investment_inr}")
            print(f"P/E        : {w.pe_ratio}" if w.pe_ratio else "P/E        : N/A")
            print(f"Mkt Cap    : Rs{w.market_cap_cr} Cr" if w.market_cap_cr else "Mkt Cap    : N/A")
            print(f"Rationale  : {w.note}")
    else:
        print("\nNo winners — no stocks passed all three stages.")
        print(f"Tip: loosen EGA band ({EGA_MIN_GAP_PCT}-{EGA_MAX_GAP_PCT}%) or MIN_EARNINGS_GROWTH ({MIN_EARNINGS_GROWTH}).")

    print("=" * 65)
    write_csv(csv_path, winners)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
