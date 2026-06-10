#!/usr/bin/env python3
"""
Nifty 200 Three-Stage Stock Screener
--------------------------------------
Stage 1: Price > 200-Day MA AND Price > 20-Day MA  (long-term trend + short-term health)
Stage 2: Piotroski F-Score >= 7                    (true YoY comparisons, not proxies)
Stage 3: 52-week high sweet spot (5-10% below) + 12-1 Month Momentum

Investment per winner: 10000 INR
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

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from filters_52w import BAND_STOCK, passes_52w_sweet_spot
from nifty200_universe import NIFTY200_TICKERS

IST = ZoneInfo("Asia/Kolkata")
INVESTMENT_INR = 10_000
PROFIT_TARGET_PCT = 3.14
PROFIT_TARGET_GAIN_INR = 500
MIN_FSCORE = 7

OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "company_name",
    "current_price_inr",
    "f_score",
    "quantity",
    "investment_inr",
    "market_cap_cr",
    "roe_pct",
    "debt_to_equity",
    "pe_ratio",
    "pb_ratio",
    "momentum_12_1_pct",
    "above_200dma",
    "note",
    "profit_target_inr",
]


@dataclass
class StockResult:
    ticker: str
    company_name: str
    current_price_inr: float
    f_score: int
    quantity: int
    investment_inr: float
    market_cap_cr: Optional[float]
    roe_pct: Optional[float]
    debt_to_equity: Optional[float]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    momentum_12_1_pct: Optional[float]
    above_200dma: bool
    note: str
    profit_target_inr: float


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


def df_row(df: pd.DataFrame, names: list[str]) -> Optional[pd.Series]:
    """Return the first matching row from a financial DataFrame by trying multiple name variants."""
    for name in names:
        if name in df.index:
            return df.loc[name]
    return None


def val(series: Optional[pd.Series], col: int) -> Optional[float]:
    """Safely extract a float from a financial series at a given column index."""
    if series is None:
        return None
    try:
        v = series.iloc[col]
        return None if pd.isna(v) else float(v)
    except (IndexError, TypeError):
        return None


def fetch_price_history(ticker: str) -> Optional[pd.DataFrame]:
    """Fetch 15 months of daily price history. Returns None if data is insufficient."""
    try:
        hist = yf.Ticker(yahoo_symbol(ticker)).history(period="15mo")
        return hist if (not hist.empty and len(hist) >= 200) else None
    except Exception:
        return None


def passes_200dma_filter(hist: pd.DataFrame) -> bool:
    sma200 = hist["Close"].rolling(200).mean().iloc[-1]
    current = hist["Close"].iloc[-1]
    return bool(current > sma200)


def passes_20dma_filter(hist: pd.DataFrame) -> bool:
    """Short-term health check: price must be above 20-day MA.
    Catches stocks in recent downtrends that still pass the long-term 200-DMA filter."""
    sma20 = hist["Close"].rolling(20).mean().iloc[-1]
    current = hist["Close"].iloc[-1]
    return bool(current > sma20)


def calculate_momentum_12_1(hist: pd.DataFrame) -> Optional[float]:
    """12-1 month return: skips the most recent month to avoid short-term mean-reversion noise."""
    if len(hist) < 252:
        return None
    price_1m = hist["Close"].iloc[-22]
    price_12m = hist["Close"].iloc[-252]
    if price_12m <= 0:
        return None
    return round((price_1m / price_12m - 1) * 100, 2)


def calculate_f_score(
    financials: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cashflow: Optional[pd.DataFrame],
) -> tuple[int, dict]:
    """
    Piotroski F-Score (0-9) using true year-over-year comparisons.
    col 0 = most recent annual period; col 1 = prior year.
    """
    score = 0
    d: dict[str, bool] = {}

    ni = df_row(financials, ["Net Income", "Net Income Common Stockholders"])
    rev = df_row(financials, ["Total Revenue", "Operating Revenue"])
    gp = df_row(financials, ["Gross Profit"])
    ta = df_row(balance_sheet, ["Total Assets"])
    td = df_row(balance_sheet, ["Total Debt"])
    eq = df_row(balance_sheet, ["Stockholders Equity", "Common Stock Equity"])
    ca = df_row(balance_sheet, ["Current Assets"])
    cl = df_row(balance_sheet, ["Current Liabilities"])
    sh = df_row(balance_sheet, ["Ordinary Shares Number", "Share Issued"])
    ocf_row = (
        df_row(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        if cashflow is not None and not cashflow.empty
        else None
    )

    ni0, ni1 = val(ni, 0), val(ni, 1)
    rev0, rev1 = val(rev, 0), val(rev, 1)
    gp0, gp1 = val(gp, 0), val(gp, 1)
    ta0, ta1 = val(ta, 0), val(ta, 1)
    td0, td1 = val(td, 0), val(td, 1)
    eq0, eq1 = val(eq, 0), val(eq, 1)
    ca0, ca1 = val(ca, 0), val(ca, 1)
    cl0, cl1 = val(cl, 0), val(cl, 1)
    sh0, sh1 = val(sh, 0), val(sh, 1)
    ocf0 = val(ocf_row, 0)

    roa0 = (ni0 / ta0) if (ni0 is not None and ta0 and ta0 > 0) else None
    roa1 = (ni1 / ta1) if (ni1 is not None and ta1 and ta1 > 0) else None

    # Profitability (4 points)
    d["positive_roa"] = bool(roa0 is not None and roa0 > 0)
    d["positive_ocf"] = bool(ocf0 is not None and ocf0 > 0)
    d["roa_improvement"] = bool(roa0 is not None and roa1 is not None and roa0 > roa1)
    d["ocf_gt_ni"] = bool(ocf0 is not None and ni0 is not None and ocf0 > ni0)

    # Leverage / Liquidity (3 points)
    de0 = (td0 / eq0) if (td0 is not None and eq0 and eq0 > 0) else None
    de1 = (td1 / eq1) if (td1 is not None and eq1 and eq1 > 0) else None
    d["de_decrease"] = bool(de0 is not None and de1 is not None and de0 < de1)

    cr0 = (ca0 / cl0) if (ca0 is not None and cl0 and cl0 > 0) else None
    cr1 = (ca1 / cl1) if (ca1 is not None and cl1 and cl1 > 0) else None
    d["cr_increase"] = bool(cr0 is not None and cr1 is not None and cr0 > cr1)

    d["no_dilution"] = bool(sh0 is not None and sh1 is not None and sh0 <= sh1)

    # Efficiency (2 points)
    gm0 = (gp0 / rev0) if (gp0 is not None and rev0 and rev0 > 0) else None
    gm1 = (gp1 / rev1) if (gp1 is not None and rev1 and rev1 > 0) else None
    d["gm_improvement"] = bool(gm0 is not None and gm1 is not None and gm0 > gm1)

    at0 = (rev0 / ta0) if (rev0 is not None and ta0 and ta0 > 0) else None
    at1 = (rev1 / ta1) if (rev1 is not None and ta1 and ta1 > 0) else None
    d["at_improvement"] = bool(at0 is not None and at1 is not None and at0 > at1)

    for v in d.values():
        score += v

    return score, d


def analyze_stock(ticker: str, hist: pd.DataFrame) -> Optional[StockResult]:
    """Stage 2+3: fetch fundamentals, compute F-score, compute momentum."""
    try:
        stock = yf.Ticker(yahoo_symbol(ticker))
        info = stock.info or {}
        if not info:
            return None

        current_price = safe_get(info, ["currentPrice", "regularMarketPrice", "previousClose"])
        if not current_price or current_price <= 0:
            return None

        try:
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow
        except Exception:
            return None

        if (
            financials is None or financials.empty
            or balance_sheet is None or balance_sheet.empty
            or financials.shape[1] < 2
            or balance_sheet.shape[1] < 2
        ):
            return None

        f_score, details = calculate_f_score(financials, balance_sheet, cashflow)
        if f_score < MIN_FSCORE:
            return None

        momentum = calculate_momentum_12_1(hist)

        market_cap = safe_get(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None

        roe = safe_get(info, ["returnOnEquity"])
        roe_pct = round(roe * 100, 2) if roe else None

        debt_to_equity = safe_get(info, ["debtToEquity"])
        if debt_to_equity is not None:
            debt_to_equity = round(debt_to_equity / 100, 2)

        pe_ratio = safe_get(info, ["trailingPE", "forwardPE"])
        pb_ratio = safe_get(info, ["priceToBook"])
        company_name = safe_get(info, ["longName", "shortName"], ticker)
        quantity = max(1, int(INVESTMENT_INR // current_price))
        investment = round(quantity * current_price, 2)
        profit_target = profit_target_price(current_price, quantity)

        y = lambda k: "Y" if details.get(k) else "N"
        mom_str = f"{momentum:+.1f}%" if momentum is not None else "N/A"
        note = (
            f"F:{f_score}/9 Trend:Above200DMA Mom:{mom_str} | "
            f"ROA:{y('positive_roa')} OCF:{y('positive_ocf')} "
            f"ROAimprv:{y('roa_improvement')} Accrual:{y('ocf_gt_ni')} "
            f"DEdown:{y('de_decrease')} CRup:{y('cr_increase')} "
            f"NoDilut:{y('no_dilution')} GMup:{y('gm_improvement')} "
            f"ATup:{y('at_improvement')}"
        )

        return StockResult(
            ticker=ticker,
            company_name=company_name,
            current_price_inr=round(current_price, 2),
            f_score=f_score,
            quantity=quantity,
            investment_inr=investment,
            market_cap_cr=market_cap_cr,
            roe_pct=roe_pct,
            debt_to_equity=debt_to_equity,
            pe_ratio=round(pe_ratio, 2) if pe_ratio else None,
            pb_ratio=round(pb_ratio, 2) if pb_ratio else None,
            momentum_12_1_pct=momentum,
            above_200dma=True,
            note=note,
            profit_target_inr=profit_target,
        )

    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
        return None


def last_recommended_ticker(csv_path: Path) -> Optional[str]:
    """Return the ticker from the last row of the output CSV, or None if unavailable."""
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
        if df.empty or "ticker" not in df.columns:
            return None
        last = df.iloc[-1]["ticker"]
        if pd.isna(last) or str(last).strip() == "":
            return None
        return str(last).strip()
    except Exception:
        return None


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
        df.loc[0, "note"] = "No stock pick available at this time"

    df = df[OUTPUT_COLUMNS]
    df.to_csv(path, index=False)
    print(f"Wrote {path}")


def main() -> int:
    root = Path(__file__).resolve().parent
    csv_path = root / "output" / "piotroski_winner.csv"
    today = datetime.now(IST).strftime("%Y-%m-%d")

    print("Nifty 200 Three-Stage Stock Screener")
    print(
        f"Stage 1: Price > 200-DMA & 20-DMA  |  Stage 2: Piotroski F >= {MIN_FSCORE}/9  |  "
        f"Stage 3: {BAND_STOCK[0]:.0f}-{BAND_STOCK[1]:.0f}% below 52wh + 12-1M Momentum"
    )
    print(
        f"Investment: Rs{INVESTMENT_INR:,}  |  Target: min(Rs{PROFIT_TARGET_GAIN_INR}, +{PROFIT_TARGET_PCT}%)  |  "
        f"Universe: {len(NIFTY200_TICKERS)} stocks  |  Date: {today}\n"
    )

    # ── Stage 1: Trend filter — 200-DMA (long-term) + 20-DMA (short-term health) ({len(NIFTY200_TICKERS)} stocks) ──
    print(f"── Stage 1: Trend filter — 200-DMA (long-term) + 20-DMA (short-term health) ({len(NIFTY200_TICKERS)} stocks) ──")
    stage1_survivors: list[tuple[str, pd.DataFrame]] = []

    for i, ticker in enumerate(NIFTY200_TICKERS, 1):
        print(f"  [{i:3d}/{len(NIFTY200_TICKERS)}] {ticker:<20}", end=" ", flush=True)
        hist = fetch_price_history(ticker)
        if hist is None:
            print("skip (no data)")
            continue
        if not passes_200dma_filter(hist):
            print("fail (below 200DMA)")
        elif not passes_20dma_filter(hist):
            print("fail (below 20DMA — short-term downtrend)")
        else:
            print("pass (above 200DMA + 20DMA)")
            stage1_survivors.append((ticker, hist))

    print(f"\nStage 1: {len(NIFTY200_TICKERS)} -> {len(stage1_survivors)} stocks above both 200-DMA and 20-DMA\n")

    # ── Stage 2: Piotroski F-Score filter ───────────────────────────────────
    print(f"── Stage 2: Piotroski F-Score filter (need >= {MIN_FSCORE}/9, true YoY) ──")
    candidates: list[StockResult] = []

    for j, (ticker, hist) in enumerate(stage1_survivors, 1):
        print(f"  [{j:3d}/{len(stage1_survivors)}] {ticker:<20}", end=" ", flush=True)
        result = analyze_stock(ticker, hist)
        if result:
            print(f"pass F:{result.f_score}/9")
            candidates.append(result)
        else:
            print(f"fail (F < {MIN_FSCORE} or missing data)")

    print(f"\nStage 2: {len(stage1_survivors)} -> {len(candidates)} stocks with F >= {MIN_FSCORE}\n")

    # ── Stage 3: 52-week sweet spot + momentum tiebreaker ───────────────────
    hist_by_ticker = {ticker: hist for ticker, hist in stage1_survivors}
    sweet_spot: list[StockResult] = []
    for c in candidates:
        hist = hist_by_ticker.get(c.ticker)
        if hist is None:
            continue
        passes, gap_pct, reason = passes_52w_sweet_spot(hist, c.current_price_inr, *BAND_STOCK)
        if passes:
            sweet_spot.append(c)
        else:
            print(f"  [52wh] Skipping {c.ticker} — {reason} (gap {gap_pct:.1f}%)")

    print(
        f"\nStage 3 pre-filter: {len(candidates)} F-qualified -> "
        f"{len(sweet_spot)} in {BAND_STOCK[0]:.0f}-{BAND_STOCK[1]:.0f}% 52wh band\n"
    )

    winner = None
    if sweet_spot:
        with_mom = [c for c in sweet_spot if c.momentum_12_1_pct is not None]
        if with_mom:
            positive = [c for c in with_mom if c.momentum_12_1_pct > 0]
            pool = positive if positive else with_mom
            ranked = sorted(pool, key=lambda x: x.momentum_12_1_pct, reverse=True)
        else:
            # Fallback: no momentum data — sort by F-score then market cap
            sweet_spot.sort(key=lambda x: (x.f_score, x.market_cap_cr or 0), reverse=True)
            ranked = sweet_spot

        # ── Deduplication: skip if same ticker as previous pick ─────────────
        prev_ticker = last_recommended_ticker(root / "output" / "piotroski_winner.csv")
        winner = None
        for candidate in ranked:
            if prev_ticker and candidate.ticker == prev_ticker:
                print(f"  [dedup] Skipping {candidate.ticker} — same as previous pick ({prev_ticker})")
                continue
            winner = candidate
            break
        if winner is None and prev_ticker:
            print(f"  [dedup] All candidates match previous pick or pool empty — no pick today")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 60)
    print("STAGE SUMMARY")
    print(f"  Stage 1 (200 DMA)  : {len(NIFTY200_TICKERS)} -> {len(stage1_survivors)} stocks")
    print(f"  Stage 2 (F >= {MIN_FSCORE})   : {len(stage1_survivors)} -> {len(candidates)} stocks")
    print(f"  Stage 3 (52wh+Momentum): {len(candidates)} -> {len(sweet_spot)} -> 1 winner")
    print("=" * 60)

    print("\nTHREE-STAGE WINNER")
    print("=" * 60)

    if winner:
        mom_str = f"{winner.momentum_12_1_pct:+.1f}%" if winner.momentum_12_1_pct is not None else "N/A"
        print(f"Stock    : {winner.ticker} ({winner.company_name})")
        print(f"Price    : Rs{winner.current_price_inr}")
        print(f"F-Score  : {winner.f_score}/9")
        print(f"Momentum : {mom_str}  (12-1 month, price)")
        print(f"Trend    : Above 200-Day Moving Average")
        print(f"Quantity : {winner.quantity} shares")
        print(f"Amount   : Rs{winner.investment_inr}")
        print(f"Mkt Cap  : Rs{winner.market_cap_cr} Cr" if winner.market_cap_cr else "Mkt Cap  : N/A")
        print(f"ROE      : {winner.roe_pct}%" if winner.roe_pct else "ROE      : N/A")
        print(f"D/E      : {winner.debt_to_equity}" if winner.debt_to_equity is not None else "D/E      : N/A")
        print(f"P/E      : {winner.pe_ratio}" if winner.pe_ratio else "P/E      : N/A")
        print(f"P/B      : {winner.pb_ratio}" if winner.pb_ratio else "P/B      : N/A")
        print(f"Criteria : {winner.note}")
    else:
        print("No winner -- no stocks passed all three stages.")
        print(f"Try lowering MIN_FSCORE (currently {MIN_FSCORE}) or check data availability.")

    print("=" * 60)

    write_csv(csv_path, winner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
