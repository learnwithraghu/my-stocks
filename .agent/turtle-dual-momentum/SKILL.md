---
name: turtle-dual-momentum
description: >-
  Screens any index or symbol universe with Richard Dennis Turtle rules plus
  Gary Antonacci dual momentum. Produces a single daily CSV (final_output_YYYYMMDD)
  with buy triggers, qty, and profit targets. Use when the user asks for turtle
  trading, dual momentum, index/ETF screening, tomorrow buy triggers, or
  final_output CSV on NSE, US, or other markets.
---

# Turtle + Dual Momentum Screener

Run a **local Python screener** (yfinance) on any index or custom symbol list. Output **one CSV per day** — same shape as the Indian ETF analyzer.

## When to use

- User wants Turtle + Dual Momentum on **any** index (Nifty ETFs, S&P sector ETFs, single country list, etc.)
- User wants `final_output_YYYYMMDD.csv` with triggers and position size
- User mentions budget per trade, profit target %, or app safety floor on triggers

## Quick start

1. Read config in [scripts/run_screener.py](scripts/run_screener.py) (`CONFIG` block at top).
2. Set: `universe`, `benchmark`, `yahoo_suffix`, `budget`, `trade_size`, `profit_target_pct`, timezone.
3. From repo root or script folder:

```bash
cd .agent/turtle-dual-momentum/scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_screener.py
```

4. Deliver **`output/final_output_YYYYMMDD.csv`** only (script deletes other CSVs in `output/`).

For the **pre-built Indian ETF** list, use `indian-etf-analyzer-python/analyze_etfs.py` instead (same CSV format).

## Required output CSV

**Filename:** `output/final_output_YYYYMMDD.csv` (date = run day in `CONFIG["timezone"]`)

**Columns (exact order):**

| Column | Description |
|--------|-------------|
| `ticker` | Symbol |
| `todays_last_price_inr` | Live/last price (rename mentally for non-INR) |
| `price_as_of` | Quote date `YYYY-MM-DD` |
| `last_eod_close_inr` | Last completed daily close |
| `tomorrow_buy_trigger_inr` | LIMIT for next session (after safety floor) |
| `profit_target_inr` | Trigger × (1 + profit_target_pct/100) |
| `qty` | floor(trade_size / trigger), min 1 |
| `amount_inr` | qty × trigger |
| `note` | `Passes all recommendation gates` or no-buy message |

**Rows:** Only symbols that pass **all** gates. If none pass, **one row** with empty ticker and note: `No ETFs to recommend at this time`.

Do **not** add extra columns (e.g. no `safety_min_trigger_inr`).

## Strategy — all gates must pass

### Turtle (Richard Dennis)

| Gate | Rule |
|------|------|
| Breakout | Close ≥ highest high of prior **55** trading days (exclude today) |
| Exit zone | Close > lowest low of prior **20** trading days (uptrend intact) |

### Dual momentum (Gary Antonacci)

| Gate | Rule |
|------|------|
| Absolute | **12M** (252 trading days) return > 0% |
| Relative | **3M** (63d) return > benchmark **3M** return |
| Score | Rank: `0.4×12M + 0.3×6M + 0.2×3M + 0.1×1M` (for ordering picks) |

### Confirmation

| Gate | Rule |
|------|------|
| RSI(14) | Between 40 and 80 |
| Volume | Today ≥ 70% of 20-day average |

## Trigger and safety

1. **Momentum trigger:** live price if 1M ≥ 3M return, else live × 0.998.
2. **App safety (always apply):** `trigger = max(momentum_trigger, last_eod_close - 0.06 + 0.01)` so broker apps requiring price above EOD−6 paise are satisfied.
3. **Profit target:** `trigger × (1 + profit_target_pct/100)` (default 3.14%).
4. **Sizing:** `qty = max(1, floor(trade_size / trigger))`, cap count at `budget // trade_size`.

## Configuring for another index

Edit `CONFIG` in `scripts/run_screener.py`:

```python
CONFIG = {
    "universe": ["SPY", "QQQ", "IWM"],      # or NSE: ["NIFTYBEES", "BANKBEES", ...]
    "benchmark": "SPY",                      # RS vs this symbol's 3M return
    "yahoo_suffix": "",                      # ".NS" for NSE, "" for US
    "budget": 300_000,
    "trade_size": 15_000,
    "profit_target_pct": 3.14,
    "max_picks": 20,
    "timezone": "Asia/Kolkata",              # or "America/New_York"
}
```

**Yahoo symbols:** NSE `TICKER.NS`, US `TICKER`, indices `^NSEI`, etc.

## Agent workflow

1. Confirm universe + benchmark + budget/trade size with user if not stated.
2. Update `CONFIG` in `run_screener.py` (or `indian-etf-analyzer-python/analyze_etfs.py` for India ETFs).
3. Run script in venv; fix any symbol with no data.
4. Read `output/final_output_*.csv` and summarize picks vs “no recommendations”.
5. Remind: delayed Yahoo data; not investment advice; run after market close for best EOD alignment.

## Reference

- Full Turtle + menu screener (Google Sheets): `claude-output.gs` in repo root
- India ETF implementation: `indian-etf-analyzer-python/analyze_etfs.py`
