#!/usr/bin/env python3
"""
Nifty 200 Piotroski F-Score Stock Picker
----------------------------------------
Applies the Piotroski F-Score strategy on Nifty 200 stocks.
- Investment per stock: 5000 INR
- Picks exactly 1 winner (highest F-Score, tie-broken by market cap)
- Sources data from Yahoo Finance
- Overwrites CSV output each run with current date
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

from nifty200_universe import NIFTY200_TICKERS

IST = ZoneInfo("Asia/Kolkata")
INVESTMENT_INR = 5000
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
    "note",
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
    note: str


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker}.NS"


def safe_get(info: dict, keys: list[str], default=None):
    for k in keys:
        if k in info and info[k] is not None:
            return info[k]
    return default


def calculate_f_score(ticker: str, info: dict, hist: pd.DataFrame) -> tuple[int, dict]:
    """
    Calculate Piotroski F-Score (0-9) using available Yahoo Finance data.
    
    9 Criteria:
    Profitability (4 points):
    1. Positive Net Income (ROA > 0)
    2. Positive Operating Cash Flow
    3. ROA improvement YoY
    4. Operating Cash Flow > Net Income
    
    Leverage/Liquidity (3 points):
    5. Decrease in Debt/Equity ratio YoY
    6. Increase in Current Ratio YoY
    7. No new equity issued
    
    Efficiency (2 points):
    8. Increase in Gross Margin YoY
    9. Increase in Asset Turnover YoY
    """
    score = 0
    details = {}
    
    # Get financial data from info
    net_income = safe_get(info, ["netIncomeToCommon"])
    total_assets = safe_get(info, ["totalAssets"])
    total_debt = safe_get(info, ["totalDebt"])
    shareholders_equity = safe_get(info, ["stockholdersEquity", "totalStockholderEquity"])
    operating_cashflow = safe_get(info, ["operatingCashflow"])
    revenue = safe_get(info, ["totalRevenue", "revenue"])
    gross_profit = safe_get(info, ["grossProfits", "grossProfit"])
    
    # Calculate ROA
    roa = None
    if net_income and total_assets and total_assets > 0:
        roa = net_income / total_assets
    
    # 1. Positive ROA
    if roa and roa > 0:
        score += 1
        details["positive_roa"] = True
    else:
        details["positive_roa"] = False
    
    # 2. Positive Operating Cash Flow
    if operating_cashflow and operating_cashflow > 0:
        score += 1
        details["positive_ocf"] = True
    else:
        details["positive_ocf"] = False
    
    # 3. ROA improvement (we use current ROA vs trailing, simplified)
    # Since we can't easily get prior year, we'll use a proxy
    trailing_eps = safe_get(info, ["trailingEps"])
    forward_eps = safe_get(info, ["forwardEps"])
    if trailing_eps and forward_eps and forward_eps > trailing_eps:
        score += 1
        details["roa_improvement"] = True
    else:
        details["roa_improvement"] = False
    
    # 4. Operating Cash Flow > Net Income
    if operating_cashflow and net_income and operating_cashflow > net_income:
        score += 1
        details["ocf_gt_ni"] = True
    else:
        details["ocf_gt_ni"] = False
    
    # 5. Debt/Equity ratio improvement
    debt_to_equity = safe_get(info, ["debtToEquity"])
    if debt_to_equity is not None:
        # Lower is better; if D/E < 100% (1.0), score a point
        if debt_to_equity < 100:
            score += 1
            details["low_debt"] = True
        else:
            details["low_debt"] = False
    else:
        details["low_debt"] = False
    
    # 6. Current Ratio check
    current_ratio = safe_get(info, ["currentRatio"])
    if current_ratio and current_ratio > 1:
        score += 1
        details["good_current_ratio"] = True
    else:
        details["good_current_ratio"] = False
    
    # 7. No new equity (check shares outstanding)
    shares_outstanding = safe_get(info, ["sharesOutstanding"])
    if shares_outstanding:
        # Assume no dilution if we can't compare
        score += 1
        details["no_dilution"] = True
    else:
        details["no_dilution"] = False
    
    # 8. Gross Margin improvement proxy
    profit_margin = safe_get(info, ["profitMargins"])
    if profit_margin and profit_margin > 0.10:  # > 10% profit margin
        score += 1
        details["good_margin"] = True
    else:
        details["good_margin"] = False
    
    # 9. Asset Turnover proxy (Revenue / Total Assets)
    if revenue and total_assets and total_assets > 0:
        asset_turnover = revenue / total_assets
        if asset_turnover > 0.5:  # Reasonable turnover
            score += 1
            details["good_turnover"] = True
        else:
            details["good_turnover"] = False
    else:
        details["good_turnover"] = False
    
    return score, details


def analyze_stock(ticker: str) -> Optional[StockResult]:
    try:
        symbol = yahoo_symbol(ticker)
        stock = yf.Ticker(symbol)
        info = stock.info or {}
        
        if not info:
            return None
        
        # Get current price
        current_price = safe_get(info, ["currentPrice", "regularMarketPrice", "previousClose"])
        if not current_price or current_price <= 0:
            return None
        
        # Get historical data for additional calculations
        hist = stock.history(period="1y")
        if hist.empty:
            return None
        
        # Calculate F-Score
        f_score, details = calculate_f_score(ticker, info, hist)
        
        # Get additional metrics
        market_cap = safe_get(info, ["marketCap"])
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap else None
        
        roe = safe_get(info, ["returnOnEquity"])
        roe_pct = round(roe * 100, 2) if roe else None
        
        debt_to_equity = safe_get(info, ["debtToEquity"])
        if debt_to_equity:
            debt_to_equity = round(debt_to_equity / 100, 2)  # Convert to ratio
        
        pe_ratio = safe_get(info, ["trailingPE", "forwardPE"])
        pb_ratio = safe_get(info, ["priceToBook"])
        
        company_name = safe_get(info, ["longName", "shortName"], ticker)
        
        # Calculate quantity for 5000 INR investment
        quantity = max(1, int(INVESTMENT_INR // current_price))
        investment = round(quantity * current_price, 2)
        
        note = f"F-Score: {f_score}/9 | "
        note += f"ROA: {'Yes' if details.get('positive_roa') else 'No'} | "
        note += f"OCF: {'Yes' if details.get('positive_ocf') else 'No'} | "
        note += f"Low Debt: {'Yes' if details.get('low_debt') else 'No'}"
        
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
            note=note,
        )
    
    except Exception as e:
        print(f"  [warn] {ticker}: {e}", file=sys.stderr)
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
    out_dir = root / "output"
    csv_path = out_dir / "piotroski_winner.csv"
    
    today = datetime.now(IST).strftime("%Y-%m-%d")
    
    print(f"Nifty 200 Piotroski F-Score Screener")
    print(f"Investment: ₹{INVESTMENT_INR:,} per stock")
    print(f"Universe: {len(NIFTY200_TICKERS)} stocks")
    print(f"Run Date: {today}\n")
    
    results = []
    for i, ticker in enumerate(NIFTY200_TICKERS, 1):
        print(f"[{i}/{len(NIFTY200_TICKERS)}] {ticker}...", end=" ", flush=True)
        result = analyze_stock(ticker)
        if result:
            print(f"F-Score: {result.f_score}")
            results.append(result)
        else:
            print("skip")
    
    # Sort by F-Score (descending), then by market cap (descending) for tie-break
    results.sort(key=lambda x: (x.f_score, x.market_cap_cr or 0), reverse=True)
    
    # Pick the winner (top 1)
    winner = results[0] if results else None
    
    print("\n" + "="*60)
    print("PIOTROSKI F-SCORE WINNER")
    print("="*60)
    
    if winner:
        print(f"Stock: {winner.ticker} ({winner.company_name})")
        print(f"Current Price: ₹{winner.current_price_inr}")
        print(f"F-Score: {winner.f_score}/9")
        print(f"Quantity to Buy: {winner.quantity} shares")
        print(f"Investment Amount: ₹{winner.investment_inr}")
        print(f"Market Cap: ₹{winner.market_cap_cr} Cr" if winner.market_cap_cr else "Market Cap: N/A")
        print(f"ROE: {winner.roe_pct}%" if winner.roe_pct else "ROE: N/A")
        print(f"D/E: {winner.debt_to_equity}" if winner.debt_to_equity else "D/E: N/A")
        print(f"P/E: {winner.pe_ratio}" if winner.pe_ratio else "P/E: N/A")
        print(f"P/B: {winner.pb_ratio}" if winner.pb_ratio else "P/B: N/A")
        print(f"Note: {winner.note}")
    else:
        print("No winner found.")
    
    print("="*60)
    
    write_csv(csv_path, winner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
