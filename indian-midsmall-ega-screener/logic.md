# Nifty Midcap + Smallcap EGA Screener — Selection Logic

## Screener Overview

Selects from **Nifty Midcap + Smallcap universe** using **Earnings Growth Acceleration (EGA)** combined with **52-week proximity**.

**Investment model:** ₹5,000 per winner (top 2 by EGA score).

**Horizon:** 2–3 week swing trades (earnings-momentum driven).

---

## Stock Selection Method: Three-Stage EGA Funnel

### Stage 1 — Price Proximity + Momentum Pre-Filter (Fast)

**Gates:**
1. Price within 10% of 52-week high
2. Positive 5-day momentum

**Why:** Quick filter for stocks in active uptrends. Avoids stale or falling names. 10% proximity = still in momentum phase.

---

### Stage 2 — Earnings Growth + Quality Gate (Detail)

Tests **earnings acceleration and revenue growth**:

| Gate | Rule |
|------|------|
| **Earnings growth** | YoY earnings growth ≥ 10% |
| **Revenue growth** | YoY revenue growth ≥ 5% |
| **RSI(14)** | Between 50 and 78 (momentum, not overbought extremes) |
| **Volume** | 5-day avg volume ≥ 80% of 20-day avg (participation) |

**Why:**
- **Earnings ≥ 10%**: Meaningful YoY growth, not noise
- **Revenue ≥ 5%**: Top-line backing (earnings growth must be real)
- **RSI 50–78**: Safe momentum zone (not oversold, not extremely stretched)
- **Volume**: Ensures liquidity for entry/exit

---

### Stage 3 — EGA Composite Score (Rank & Select)

All Stage 2 survivors are ranked by **EGA composite score**:

```
EGA score = weighted combination of:
  - Earnings growth rate
  - Revenue growth rate
  - Current price proximity to 52-week high
  - 5-day momentum
  - RSI(14)
  - Volume ratio
```

**Selection:** Top 2 stocks by EGA score.

**Why:** EGA captures **earnings momentum** + **price momentum** together. Top 2 = diversification (2 eggs, 2 baskets) while keeping capital focused.

---

## Trade Logic — Buy Order Setup

For each of the top 2 winners:

1. **Buy trigger (LIMIT price)**
   - Use live price (earnings momentum doesn't wait)
   - Apply **app safety floor**: must be above `(last EOD close − ₹0.06) + ₹0.01` on NSE

2. **Profit target** = trigger × 1.0314 (+3.14%)

3. **Quantity** = `₹5,000 ÷ trigger` (whole shares)

4. **Amount** = ₹5,000 per stock (₹10,000 total for 2 winners)

---

## Output

**File:** `output/final_output_YYYYMMDD.csv`

**Columns:** `date`, `ticker`, `company_name`, `current_price_inr`, `quantity`, `investment_inr`, `earnings_growth_pct`, `revenue_growth_pct`, `gap_to_52wh_pct`, `momentum_5d_pct`, `rsi_14`, `ega_score`, `pe_ratio`, `market_cap_cr`, `note`

- Top 2 rows: the 2 stocks with highest EGA scores (both passing Stage 1–2)
- If fewer than 2 pass: fewer rows (e.g., 1 if only 1 survivor, 0 if none)
- If none pass: `No stocks to recommend at this time`
- Previous output files are cleaned up automatically

---

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Universe | Nifty Midcap + Smallcap | Growth-focused mid/small caps |
| Stage 1 — Proximity | ≤ 10% below 52-week high | Momentum proximity |
| Stage 1 — Momentum | 5-day return > 0% | Recent uptrend confirmation |
| Stage 2 — Earnings | YoY growth ≥ 10% | Meaningful growth |
| Stage 2 — Revenue | YoY growth ≥ 5% | Top-line backing |
| Stage 2 — RSI | 50–78 (inclusive) | Safe momentum zone |
| Stage 2 — Volume | 5-day avg ≥ 80% of 20-day avg | Liquidity confirmation |
| Stage 3 — Selection | Top 2 by EGA score | Dual diversification |
| 52-week window | ~252 trading days | Full-year high reference |
| 5-day window | ~5 trading days | Short-term momentum |
| RSI period | 14 | Standard momentum oscillator |
| Investment per winner | ₹5,000 | Fixed allocation |
| Max winners | 2 | Top 2 by EGA score |

---

## Rationale

**EGA (Earnings Growth Acceleration)** + **52-Week Proximity** target:
- **Growth stocks in momentum** — earnings + price both accelerating
- **Mid/smallcap sweet spot** — higher growth potential than large-caps
- **Short horizon (2-3 weeks)** — earnings acceleration is time-limited; quick entry/exit
- **Top 2 only** — quality over quantity; avoids dilution

**Why earnings growth?**
- **Real growth**, not just price momentum
- **Earnings acceleration** = inflection point (market often reprices on earnings surprises)
- **Revenue backing** ensures quality (top-line growth, not accounting tricks)

**Why proximity to 52-week high?**
- Flags stocks in active momentum
- Avoids "cheap" traps (far from 52W high = momentum already broken)
- Combined with earnings, finds growth stories market is *currently* rewarding

This is **earnings-momentum swing trading**, suited for:
- Growth investors with a 2–3 week horizon
- Traders who monitor earnings calendar for inflection points
- Mid/smallcap focused portfolios

---

## Universe

The universe is **Nifty Midcap + Smallcap** — a dynamic set of growth-oriented stocks. Edit `midsmall_universe.py` to adjust the stock list based on your filtering criteria (e.g., minimum market cap).

---

## Sources

- EGA concept builds on earnings momentum research (e.g., Foerster, S. R., et al., "The good name of a stockholder: Cascades, reputational complementarities, and earnings surprises").
- 52-week high proximity: classic momentum signal (Jegadeesh & Titman, "Returns to buying winners and selling losers: Implications for stock market efficiency").
