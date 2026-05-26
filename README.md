# my-stocks

Stock and ETF screening with **Turtle trading** + **dual momentum**, local Python runners, and an agent skill for any index.

## How we pick stocks — 7 steps

Every Turtle + Dual Momentum stock screener (e.g. Nifty 100) follows the same pipeline. **All gates must pass** — one failure and the symbol is skipped.

### Step 1 — Start with a fixed universe

We do not scan the whole market. Each project has a predefined list:

| Project | Universe | Benchmark (for relative strength) |
|---------|----------|----------------------------------|
| Nifty 100 | 100 NSE large-caps | NIFTYBEES |

The Indian **ETF** analyzer uses the same momentum idea but a smaller ETF list and a lighter Turtle rule (20-day exit only, no 55-day breakout).

### Step 2 — Pull price data

For each symbol we download ~2 years of daily OHLCV from Yahoo Finance and fetch a **live/last price** (falls back to the last completed daily close if live is unavailable).

### Step 3 — Turtle trend gates (Richard Dennis)

Turtle trading asks: *is price breaking out in an uptrend?*

| Gate | Rule |
|------|------|
| **55-day breakout** | Live price ≥ highest high of the prior **55** trading days (today excluded) |
| **20-day exit zone** | Live price > lowest low of the prior **20** trading days (uptrend still intact) |

Both must be true. This filters for symbols in a confirmed upward move, not a dead cat bounce.

### Step 4 — Dual momentum gates (Gary Antonacci)

Dual momentum combines **absolute** and **relative** strength:

| Gate | Rule |
|------|------|
| **Absolute momentum** | 12-month return (252 trading days) **> 0%** — only assets going up over the year |
| **Relative momentum** | 3-month return (63 days) **beats the benchmark's** 3-month return (e.g. stock beats NIFTYBEES) |

A symbol must be winning on its own *and* beating the market proxy.

### Step 5 — Confirmation filters

Two extra sanity checks before we trust the signal:

| Filter | Rule |
|--------|------|
| **RSI(14)** | Between **40 and 80** — not oversold junk, not extremely overbought |
| **Volume** | Today's volume ≥ **70%** of the 20-day average — enough participation |

### Step 6 — Rank survivors and pick the best

Every symbol that passed Steps 3–5 gets a **momentum score**:

```
score = 0.4 × 12M return + 0.3 × 6M return + 0.2 × 3M return + 0.1 × 1M return
```

We sort by score (highest first). **Nifty 100** keeps up to 20 whole-share slots:

| Project | Budget per row | Output |
|---------|----------------|--------|
| Nifty 100 | ₹15,000 each (up to 20 slots) | Whole shares |

### Step 7 — Set tomorrow's buy order

For each final pick we compute:

1. **Buy trigger (LIMIT price)**  
   - If 1-month return ≥ 3-month return → trigger = live price  
   - Else → trigger = live price × 0.998 (slightly below, for a pullback entry)  
   - Then raise trigger if needed for **app safety**: must be above `(last EOD close − ₹0.06) + ₹0.01` on NSE

2. **Profit target** = trigger × **1.0314** (+3.14%)

3. **Quantity** — Nifty 100 / India ETF: `max(1, floor(trade_size ÷ trigger))` whole shares.

4. **Amount** = qty × trigger (within budget for India)

Output lands in `output/final_output_YYYYMMDD.csv`. If **no symbol passes all gates**, the CSV has one row: `No stocks to recommend at this time`.

---

## Projects

| Path | Description |
|------|-------------|
| [`indian-etf-analyzer-python/`](indian-etf-analyzer-python/) | 25 Indian ETFs → `final_output_YYYYMMDD.csv` |
| [`indian-nifty100-analyzer-python/`](indian-nifty100-analyzer-python/) | Nifty 100 stocks, Turtle + Dual Momentum |
| [`indian-nifty200-piotroski/`](indian-nifty200-piotroski/) | Nifty 200 stocks, Piotroski F-Score (1 winner, ₹5000 investment) |
| [`indian-midsmall-ega-screener/`](indian-midsmall-ega-screener/) | Nifty Midcap + Smallcap, Earnings Growth Acceleration (2 winners, ₹5000 each) |
| [`.agent/turtle-dual-momentum/`](.agent/turtle-dual-momentum/) | Agent skill + generic `run_screener.py` for any universe |

## Quick start

### 1. Enable virtual environment (always required)

```bash
# From the project root
cd /Users/raghunandanask/Desktop/github-repo/finopsai-course
source venv/bin/activate
```

> **Note:** Run `source venv/bin/activate` every time before running any script.

### 2. Run all Python screeners at once

```bash
# Run all analyzers in one command
python3 indian-etf-analyzer-python/analyze_etfs.py && \
python3 indian-nifty100-analyzer-python/analyze_stocks.py && \
python3 indian-nifty200-piotroski/analyze_piotroski.py && \
python3 indian-midsmall-ega-screener/analyze_stocks.py
```

### 3. Run individual screeners

```bash
# Indian ETF Analyzer
cd indian-etf-analyzer-python
python3 analyze_etfs.py

# Nifty 100 Turtle + Dual Momentum
cd ../indian-nifty100-analyzer-python
python3 analyze_stocks.py

# Nifty 200 Piotroski F-Score (1 winner, ₹5000 investment)
cd ../indian-nifty200-piotroski
python3 analyze_piotroski.py

# Nifty Midcap + Smallcap EGA (2 winners, ₹5000 per stock)
cd ../indian-midsmall-ega-screener
python3 analyze_stocks.py
```

See each folder's README for config (budget ₹3L, ₹15K/trade, 3.14% profit target).

## Disclaimer

Screening tool only — not investment advice. Prices via Yahoo Finance may be delayed.
