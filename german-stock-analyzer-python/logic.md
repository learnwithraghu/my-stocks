# German Stock Analyzer — Selection Logic

## Screener Overview

Selects from **top 50 German large-caps** (DAX 40 + MDAX leaders) using **Turtle Trading + Dual Momentum** framework.

**Investment model:** $50 USD per recommendation (fractional shares supported; XETRA prices converted via EUR/USD).

**Horizon:** Daily signals (short-term momentum traders).

---

## Stock Selection Method: Turtle Trading + Dual Momentum

### Stage 1 — Turtle Trend Gates (Richard Dennis)

Tests whether price is in an uptrend:

| Gate | Rule |
|------|------|
| **55-day breakout** | Live price ≥ highest high of the prior 55 trading days (excluding today) |
| **20-day exit zone** | Live price > lowest low of the prior 20 trading days |

**Why:** Filters for confirmed upward moves, not mean-reversion bounces.

---

### Stage 2 — Dual Momentum Gates (Gary Antonacci)

Combines absolute + relative strength:

| Gate | Rule |
|------|------|
| **Absolute momentum** | 12-month return > 0% (stock going up over a year) |
| **Relative momentum** | 3-month return beats **EXS1** (DAX ETF) 3-month return (market outperformance) |

**Why:** Only buys stocks winning on their own *and* outpacing the German equity market.

---

### Stage 3 — Confirmation Filters

Two sanity checks before the signal is trusted:

| Filter | Rule |
|--------|------|
| **RSI(14)** | Between 40 and 80 (not oversold, not extremely overbought) |
| **Volume** | Today's volume ≥ 70% of 20-day average (participation exists) |

**Why:** Filters out weak signals and low-volume noise.

---

### Stage 4 — Rank & Select

All stocks passing Stages 1–3 are ranked by **momentum score**:

```
score = 0.4 × 12M return + 0.3 × 6M return + 0.2 × 3M return + 0.1 × 1M return
```

**All stocks that pass** are recommended (no upper slot limit, no minimum price). Fractional shares supported.

---

## Trade Logic — Buy Order Setup

For each picked stock:

1. **Buy trigger (LIMIT price)**
   - If 1M return ≥ 3M return → use live price
   - Else → use live price × 0.998 (pullback entry)
   - Apply **app safety floor**: must be above `(last EOD close − $0.01) + $0.01`

2. **Profit target** = trigger × 1.0314 (+3.14%)

3. **Quantity** = `$50 ÷ trigger` (fractional shares)

4. **Amount** ≈ **$50 USD** per stock

---

## Output

**File:** `output/final_output_YYYYMMDD.csv`

**Columns:** `ticker`, `todays_last_price_inr`, `price_as_of`, `last_eod_close_inr`, `tomorrow_buy_trigger_inr`, `profit_target_inr`, `qty`, `amount_inr`, `note`

(Column names kept for compatibility; values are in USD)

- **All stocks** that pass all gates (Stages 1–3), ranked by momentum score
- If none pass: `No stocks to recommend at this time`
- Previous output files are cleaned up automatically

---

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Universe | 50 German large-caps | DAX 40 + MDAX leaders |
| Benchmark | EXS1 | iShares Core DAX ETF (XETRA) |
| 55-day window | 55 trading days | Turtle breakout threshold |
| 20-day window | 20 trading days | Turtle exit zone |
| 12-month window | 252 trading days | Absolute momentum period |
| 3-month window | 63 trading days | Relative momentum period |
| RSI period | 14 | Standard momentum oscillator |
| Volume threshold | 70% | Of 20-day average |
| Profit target | 3.14% | Fixed per recommendation |
| Per-pick allocation | $50 USD | Fractional shares OK |
| Fractional shares | Supported | Any share price OK |
| Currency conversion | EUR/USD live rate | XETRA prices to USD |

---

## Rationale

**Turtle Trading** + **Dual Momentum** combine:
- **Trend-following** (breakouts) — catches large moves
- **Momentum confirmation** — avoids false signals in sideways markets
- **Market context** (relative strength) — ignores stocks lagging the DAX
- **Volatility filters** (RSI, volume) — skips overextended or low-conviction moves

This is **short-term tactical**, suitable for swing traders or daily alert users who trade German equities.

**Fractional share support** + **live EUR/USD conversion** allow:
- Small allocations ($50/stock) suitable for diversification
- Automatic currency conversion from XETRA prices
- Low capital requirements
- Access to German blue-chips with minimal per-position risk

---

## Universe

German stock constituents are periodically refreshed from:
- [DAX indices](https://www.dax-indices.com/)
- [MDAX indices](https://www.dax-indices.com/)

Edit `de_universe.py` to update the ticker list.
