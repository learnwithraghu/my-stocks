#!/usr/bin/env python3
"""
Nifty Midcap 100 PEAD Daily Winner Screener
--------------------------------------------
Stage 1 (traditional) : 200 DMA + RSI(14) 45-75 + volume confirmation
Stage 2 (modern)    : Post-Earnings Announcement Drift (PEAD) surprise + drift
Stage 3 (tiebreaker): 12-1 month momentum rank -> 1 winner

Investment: Rs 10,000 per winner (whole shares)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
import yfinance as yf

from midcap100_universe import NIFTY_MIDCAP100_TICKERS

IST = ZoneInfo("Asia/Kolkata")
INVESTMENT_INR = 10_000
PROFIT_TARGET_PCT = 3.14
PROFIT_TARGET_GAIN_INR = 500
RSI_MIN = 45
RSI_MAX = 75
MIN_VOLUME_RATIO = 0.70
MAX_EARNINGS_DAYS = 30
MIN_SURPRISE_ESTIMATE = 0.03
MIN_SURPRISE_QOQ = 0.08
MIN_SURPRISE_INFO = 0.10
MAX_DRIFT_GAP = 0.15

OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "company_name",
    "current_price_inr",
    "quantity",
    "investment_inr",
    "surprise_pct",
    "earnings_days_ago",
    "momentum_12_1_pct",
    "above_200dma",
    "rsi_14",
    "gap_to_52wh_pct",
    "pe_ratio",
    "market_cap_cr",
    "pead_rank_score",
    "note",
    "profit_target_inr",
]


@dataclass
class StockResult:
    ticker: str
    company_name: str
    current_price_inr: float
    quantity: int
    investment_inr: float
    surprise_pct: float
    earnings_days_ago: int
    momentum_12_1_pct: Optional[float]
    above_200dma: bool
    rsi_14: float
    gap_to_52wh_pct: float
    pe_ratio: Optional[float]
    market_cap_cr: Optional[float]
    pead_rank_score: float
    note: str
    profit_target_inr: float


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def profit_target_price(entry_price: float, quantity: int) -> float:
    pct_target = entry_price * (1 + PROFIT_TARGET_PCT / 100)
    fixed_gain_target = entry_price + (PROFIT_TARGET_GAIN_INR / max(quantity, 1))
    return round(min(pct_target, fixed_gain_target), 2)


def safe_get_val(info: dict, keys: list[str], default=None):
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


def fetch_price_history(ticker: str) -> Optional[pd.DataFrame]:
    try:
        hist = yf.Ticker(yahoo_symbol(ticker)).history(period="15mo")
        return hist if (not hist.empty and len(hist) >= 200) else None
    except Exception:
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


def passes_stage1(hist: pd.DataFrame) -> tuple[bool, float]:
    """200 DMA, volume, RSI. Returns (passes, rsi)."""
    sma200 = hist["Close"].rolling(200).mean().iloc[-1]
    current = hist["Close"].iloc[-1]
    if not (current > sma200):
        return False, 0.0

    rsi = calculate_rsi(hist["Close"])
    if rsi is None or not (RSI_MIN <= rsi <= RSI_MAX):
        return False, rsi or 0.0

    if len(hist) >= 20:
        vol_today = hist["Volume"].iloc[-1]
        vol_20d = hist["Volume"].iloc[-20:].mean()
        if vol_20d > 0 and (vol_today / vol_20d) < MIN_VOLUME_RATIO:
            return False, rsi

    return True, rsi


def calculate_momentum_12_1(hist: pd.DataFrame) -> Optional[float]:
    if len(hist) < 252:
        return None
    price_1m = hist["Close"].iloc[-22]
    price_12m = hist["Close"].iloc[-252]
    if price_12m <= 0:
        return None
    return round((price_1m / price_12m - 1) * 100, 2)


def _normalize_earnings_index(ed: pd.DataFrame) -> pd.DataFrame:
    if ed is None or ed.empty:
        return ed
    out = ed.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    out = out.sort_index(ascending=False)
    return out.dropna(how="all")


def _days_ago(report_dt: pd.Timestamp, now: datetime) -> int:
    if report_dt.tzinfo is None:
        report_dt = report_dt.tz_localize(IST)
    else:
        report_dt = report_dt.tz_convert(IST)
    now_ist = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    return max(0, (now_ist.date() - report_dt.date()).days)


def surprise_from_earnings_dates(
    stock: yf.Ticker, now: datetime
) -> tuple[bool, float, int, str]:
    """Preferred PEAD path: epsActual vs epsEstimate from earnings_dates."""
    try:
        ed = _normalize_earnings_index(stock.earnings_dates)
    except Exception:
        ed = None

    if ed is None or ed.empty:
        return False, 0.0, 999, ""

    col_map = {str(c).lower(): c for c in ed.columns}
    est_col = None
    act_col = None
    surprise_col = None
    for key, orig in col_map.items():
        if "estimate" in key and "eps" in key:
            est_col = orig
        elif "reported" in key and "eps" in key:
            act_col = orig
        elif "surprise" in key:
            surprise_col = orig

    for report_dt, row in ed.iterrows():
        if pd.isna(report_dt):
            continue
        days = _days_ago(report_dt, now)
        if days > MAX_EARNINGS_DAYS:
            continue

        surprise_pct: Optional[float] = None
        if surprise_col is not None and not pd.isna(row.get(surprise_col)):
            surprise_pct = float(row[surprise_col])
        elif act_col and est_col:
            actual = row.get(act_col)
            estimate = row.get(est_col)
            if actual is not None and estimate is not None and not pd.isna(actual) and not pd.isna(estimate):
                est_f = float(estimate)
                act_f = float(actual)
                if abs(est_f) > 1e-9:
                    surprise_pct = ((act_f - est_f) / abs(est_f)) * 100

        if surprise_pct is None:
            continue
        if surprise_pct >= MIN_SURPRISE_ESTIMATE * 100:
            return True, round(surprise_pct, 2), days, "earnings_dates"
        return False, round(surprise_pct, 2), days, "earnings_dates_low"

    return False, 0.0, 999, ""


def surprise_from_quarterly_financials(stock: yf.Ticker) -> tuple[bool, float, str]:
    """Fallback A: QoQ net income jump from quarterly financials."""
    try:
        qf = stock.quarterly_financials
        if qf is None or qf.empty or qf.shape[1] < 2:
            qf = stock.quarterly_income_stmt
        if qf is None or qf.empty or qf.shape[1] < 2:
            return False, 0.0, ""

        ni = df_row(qf, ["Net Income", "Net Income Common Stockholders"])
        ni0, ni1 = val(ni, 0), val(ni, 1)
        if ni0 is None or ni1 is None or abs(ni1) < 1e-9:
            return False, 0.0, ""

        surprise = (ni0 - ni1) / abs(ni1)
        surprise_pct = round(surprise * 100, 2)
        if surprise >= MIN_SURPRISE_QOQ:
            return True, surprise_pct, "quarterly_qoq"
        return False, surprise_pct, "quarterly_qoq_low"
    except Exception:
        return False, 0.0, ""


def surprise_from_info(info: dict) -> tuple[bool, float, str]:
    """Fallback B: earningsQuarterlyGrowth from info."""
    eq = safe_get_val(info, ["earningsQuarterlyGrowth", "earningsGrowth"])
    if eq is None:
        return False, 0.0, ""
    surprise_pct = round(float(eq) * 100, 2)
    if float(eq) >= MIN_SURPRISE_INFO:
        return True, surprise_pct, "info_quarterly_growth"
    return False, surprise_pct, "info_quarterly_growth_low"


def earnings_recency_days(stock: yf.Ticker, info: dict, now: datetime) -> int:
    """Days since last earnings report (for fallback B gate)."""
    try:
        ed = _normalize_earnings_index(stock.earnings_dates)
        if ed is not None and not ed.empty:
            latest = ed.index[0]
            if not pd.isna(latest):
                return _days_ago(latest, now)
    except Exception:
        pass

    cal = info.get("earningsTimestamp") or info.get("mostRecentQuarter")
    if cal:
        try:
            ts = pd.to_datetime(cal, unit="s" if isinstance(cal, (int, float)) else None)
            return _days_ago(ts, now)
        except Exception:
            pass
    return 999


def passes_drift_filter(info: dict, hist: pd.DataFrame) -> tuple[bool, float, float]:
    """Within 15% of 52-week high and 5-day return >= 0."""
    current = safe_get_val(info, ["currentPrice", "regularMarketPrice", "previousClose"])
    high_52w = safe_get_val(info, ["fiftyTwoWeekHigh"])
    if not current or not high_52w or high_52w <= 0:
        return False, 0.0, 0.0

    gap_pct = round((high_52w - current) / high_52w * 100, 2)
    if len(hist) < 6:
        return False, gap_pct, 0.0

    momentum_5d = round((hist["Close"].iloc[-1] / hist["Close"].iloc[-6] - 1) * 100, 2)
    passes = (gap_pct <= MAX_DRIFT_GAP * 100) and (momentum_5d >= 0)
    return passes, gap_pct, momentum_5d


def check_pead(
    stock: yf.Ticker, info: dict, hist: pd.DataFrame, now: datetime
) -> tuple[bool, float, int, str]:
    """
    Returns (passes, surprise_pct, earnings_days_ago, surprise_method).
    """
    ok, surprise_pct, days, method = surprise_from_earnings_dates(stock, now)
    if ok and days <= MAX_EARNINGS_DAYS:
        passes_drift, _, _ = passes_drift_filter(info, hist)
        if passes_drift:
            return True, surprise_pct, days, method

    ok, surprise_pct, method = surprise_from_quarterly_financials(stock)
    if ok:
        days = earnings_recency_days(stock, info, now)
        if days <= MAX_EARNINGS_DAYS:
            passes_drift, _, _ = passes_drift_filter(info, hist)
            if passes_drift:
                return True, surprise_pct, days, method

    ok, surprise_pct, method = surprise_from_info(info)
    if ok:
        days = earnings_recency_days(stock, info, now)
        if days <= MAX_EARNINGS_DAYS:
            passes_drift, _, _ = passes_drift_filter(info, hist)
            if passes_drift:
                return True, surprise_pct, days, method

    return False, 0.0, 999, ""


def pead_rank_score(surprise_pct: float, momentum_12_1: Optional[float]) -> float:
    mom = momentum_12_1 if momentum_12_1 is not None else 0.0
    return round(0.50 * surprise_pct + 0.50 * mom, 4)


def analyze_stock(
    ticker: str, hist: pd.DataFrame, rsi: float, now: datetime
) -> Optional[StockResult]:
    try:
        stock = yf.Ticker(yahoo_symbol(ticker))
        info = stock.info or {}
        if not info:
            return None

        passes_pead, surprise_pct, earnings_days, method = check_pead(stock, info, hist, now)
        if not passes_pead:
            return None

        current_price = safe_get_val(info, ["currentPrice", "regularMarketPrice", "previousClose"])
        if not current_price or current_price <= 0:
            return None

        _, gap_pct, mom_5d = passes_drift_filter(info, hist)
        momentum = calculate_momentum_12_1(hist)
        rank = pead_rank_score(surprise_pct, momentum)

        market_cap = safe_get_val(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None
        pe_ratio = safe_get_val(info, ["trailingPE", "forwardPE"])
        company_name = safe_get_val(info, ["longName", "shortName"], ticker) or ticker
        quantity = max(1, int(INVESTMENT_INR // current_price))
        investment = round(quantity * current_price, 2)
        profit_target = profit_target_price(current_price, quantity)

        mom_str = f"{momentum:+.1f}%" if momentum is not None else "N/A"
        note = (
            f"PEAD:{method} Surprise:{surprise_pct:+.1f}% "
            f"Earnings:{earnings_days}d ago | 52wh_gap:{gap_pct:.1f}% "
            f"5d:{mom_5d:+.1f}% Mom12-1:{mom_str} RSI:{rsi:.1f}"
        )

        return StockResult(
            ticker=ticker,
            company_name=company_name,
            current_price_inr=round(current_price, 2),
            quantity=quantity,
            investment_inr=investment,
            surprise_pct=surprise_pct,
            earnings_days_ago=earnings_days,
            momentum_12_1_pct=momentum,
            above_200dma=True,
            rsi_14=rsi,
            gap_to_52wh_pct=gap_pct,
            pe_ratio=round(pe_ratio, 2) if pe_ratio else None,
            market_cap_cr=market_cap_cr,
            pead_rank_score=rank,
            note=note,
            profit_target_inr=profit_target,
        )
    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None


def pick_winner(candidates: list[StockResult]) -> Optional[StockResult]:
    if not candidates:
        return None

    def sort_key(c: StockResult) -> tuple:
        mom = c.momentum_12_1_pct if c.momentum_12_1_pct is not None else -999.0
        cap = c.market_cap_cr or 0.0
        return (c.pead_rank_score, c.surprise_pct, cap, mom)

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
    csv_path = root / "output" / "midcap_winner.csv"
    today = datetime.now(IST).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)

    print("Nifty Midcap 100 PEAD Daily Winner Screener")
    print("Stage 1: 200 DMA + RSI + Volume  |  Stage 2: PEAD surprise + drift  |  Stage 3: 12-1M rank")
    print(
        f"Investment: Rs{INVESTMENT_INR:,}  |  Target: min(Rs{PROFIT_TARGET_GAIN_INR}, +{PROFIT_TARGET_PCT}%)  |  "
        f"Universe: {len(NIFTY_MIDCAP100_TICKERS)} stocks  |  Date: {today}\n"
    )

    print(f"── Stage 1: 200 DMA + RSI({RSI_MIN}-{RSI_MAX}) + volume ({len(NIFTY_MIDCAP100_TICKERS)} stocks) ──")
    stage1_survivors: list[tuple[str, pd.DataFrame, float]] = []

    for i, ticker in enumerate(NIFTY_MIDCAP100_TICKERS, 1):
        print(f"  [{i:3d}/{len(NIFTY_MIDCAP100_TICKERS)}] {ticker:<20}", end=" ", flush=True)
        hist = fetch_price_history(ticker)
        if hist is None:
            print("skip (no data)")
            continue
        ok, rsi = passes_stage1(hist)
        if ok:
            print(f"pass  RSI:{rsi:.1f}")
            stage1_survivors.append((ticker, hist, rsi))
        else:
            print(f"fail  RSI:{rsi:.1f}")

    print(f"\nStage 1: {len(NIFTY_MIDCAP100_TICKERS)} -> {len(stage1_survivors)} stocks\n")

    print(
        f"── Stage 2: PEAD (earnings <= {MAX_EARNINGS_DAYS}d, surprise, drift <= {MAX_DRIFT_GAP*100:.0f}% from 52wh) ──"
    )
    candidates: list[StockResult] = []

    for j, (ticker, hist, rsi) in enumerate(stage1_survivors, 1):
        print(f"  [{j:3d}/{len(stage1_survivors)}] {ticker:<20}", end=" ", flush=True)
        result = analyze_stock(ticker, hist, rsi, now)
        if result:
            print(
                f"pass  surprise:{result.surprise_pct:+.1f}%  "
                f"{result.earnings_days_ago}d ago  rank:{result.pead_rank_score:.2f}"
            )
            candidates.append(result)
        else:
            print("fail (PEAD/drift)")

    print(f"\nStage 2: {len(stage1_survivors)} -> {len(candidates)} PEAD candidates\n")

    winner = pick_winner(candidates)

    print("=" * 60)
    print("STAGE SUMMARY")
    print(f"  Stage 1 (200 DMA)  : {len(NIFTY_MIDCAP100_TICKERS)} -> {len(stage1_survivors)}")
    print(f"  Stage 2 (PEAD)     : {len(stage1_survivors)} -> {len(candidates)}")
    print(f"  Stage 3 (1 winner) : {len(candidates)} -> {1 if winner else 0}")
    print("=" * 60)

    print("\nMIDCAP PEAD WINNER")
    print("=" * 60)
    if winner:
        mom_str = f"{winner.momentum_12_1_pct:+.1f}%" if winner.momentum_12_1_pct is not None else "N/A"
        print(f"Stock     : {winner.ticker} ({winner.company_name})")
        print(f"Price     : Rs{winner.current_price_inr}")
        print(f"Surprise  : {winner.surprise_pct:+.1f}%  ({winner.earnings_days_ago} days since earnings)")
        print(f"PEAD rank : {winner.pead_rank_score:.2f}  (12-1M mom: {mom_str})")
        print(f"RSI(14)   : {winner.rsi_14:.1f}  |  52wh gap: {winner.gap_to_52wh_pct:.1f}%")
        print(f"Quantity  : {winner.quantity} shares  |  Amount: Rs{winner.investment_inr}")
        print(f"Mkt Cap   : Rs{winner.market_cap_cr} Cr" if winner.market_cap_cr else "Mkt Cap   : N/A")
        print(f"Criteria  : {winner.note}")
    else:
        print("No winner — no stocks passed all three stages.")

    print("=" * 60)
    write_csv(csv_path, winner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
