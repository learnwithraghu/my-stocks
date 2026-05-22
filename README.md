# my-stocks

Stock and ETF screening with **Turtle trading** + **dual momentum**, local Python runners, and an agent skill for any index.

## How we pick stocks — 7 steps

Every stock screener (Nifty 100, US, German) follows the same pipeline. **All gates must pass** — one failure and the symbol is skipped.

### Step 1 — Start with a fixed universe

We do not scan the whole market. Each project has a predefined list:

| Project | Universe | Benchmark (for relative strength) |
|---------|----------|----------------------------------|
| Nifty 100 | 100 NSE large-caps | NIFTYBEES |
| US stocks | ~96 S&P-style names | SPY |
| German stocks | Top 50 DAX + MDAX | EXS1 (DAX ETF) |

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
| **Relative momentum** | 3-month return (63 days) **beats the benchmark’s** 3-month return (e.g. stock beats SPY) |

A symbol must be winning on its own *and* beating the market proxy.

### Step 5 — Confirmation filters

Two extra sanity checks before we trust the signal:

| Filter | Rule |
|--------|------|
| **RSI(14)** | Between **40 and 80** — not oversold junk, not extremely overbought |
| **Volume** | Today’s volume ≥ **70%** of the 20-day average — enough participation |

### Step 6 — Rank survivors and pick the best

Every symbol that passed Steps 3–5 gets a **momentum score**:

```
score = 0.4 × 12M return + 0.3 × 6M return + 0.2 × 3M return + 0.1 × 1M return
```

We sort by score (highest first). **US and German** screeners list **every symbol that passes** all gates (no share-price cap — fractional shares OK). **Nifty 100** keeps up to 20 whole-share slots:

| Project | Budget per row | Output |
|---------|----------------|--------|
| Nifty 100 | ₹15,000 each (up to 20 slots) | Whole shares |
| US / German | $50 fractional per row | All gate passers |

### Step 7 — Set tomorrow’s buy order

For each final pick we compute:

1. **Buy trigger (LIMIT price)**  
   - If 1-month return ≥ 3-month return → trigger = live price  
   - Else → trigger = live price × 0.998 (slightly below, for a pullback entry)  
   - Then raise trigger if needed for **app safety**: must be above `(last EOD close − ₹0.06) + ₹0.01` on NSE, or `(EOD − $0.01) + $0.01` on US/German

2. **Profit target** = trigger × **1.0314** (+3.14%)

3. **Quantity** — Nifty 100 / India ETF: `max(1, floor(trade_size ÷ trigger))` whole shares. **US / German:** fractional `qty = $50 ÷ trigger` (any share price OK).

4. **Amount** = qty × trigger (≈ $50 for US/German rows; within budget for India)

Output lands in `output/final_output_YYYYMMDD.csv`. If **no symbol passes all gates**, the CSV has one row: `No stocks to recommend at this time`.

---

## Projects

| Path | Description |
|------|-------------|
| [`indian-etf-analyzer-python/`](indian-etf-analyzer-python/) | 25 Indian ETFs → `final_output_YYYYMMDD.csv` |
| [`indian-nifty100-analyzer-python/`](indian-nifty100-analyzer-python/) | Nifty 100 stocks, Turtle + Dual Momentum |
| [`us-stock-analyzer-python/`](us-stock-analyzer-python/) | US large-cap stocks, **$50 fractional** per pick |
| [`german-stock-analyzer-python/`](german-stock-analyzer-python/) | Top 50 German stocks, **$50 fractional USD** per pick |
| [`.agent/turtle-dual-momentum/`](.agent/turtle-dual-momentum/) | Agent skill + generic `run_screener.py` for any universe |

## Quick start

```bash
cd indian-etf-analyzer-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python analyze_etfs.py
```

See each folder’s README for config (budget ₹3L, ₹15K/trade, 3.14% profit target).

## Disclaimer

Screening tool only — not investment advice. Prices via Yahoo Finance may be delayed.
