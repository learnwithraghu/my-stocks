# Indian ETF Analyzer — Selection Logic

## Screener Overview

Selects from **25 Indian ETFs** using **Turtle Trading + Dual Momentum** framework.

**Investment model:** ₹15,000 per recommendation (max 2 picks).

**Horizon:** Daily signals (short-term momentum traders).

**52-week high gate:** 4–12% below 52-week high; no fresh 52-week high in the last 10 trading days.

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
| **Absolute momentum** | 12-month return > 0% (asset going up over a year) |
| **Relative momentum** | 3-month return beats **NIFTYBEES** 3-month return (market outperformance) |

**Why:** Only buys assets winning on their own *and* outpacing the broad market.

---

### Stage 3 — Confirmation Filters

Two sanity checks before the signal is trusted:

| Filter | Rule |
|--------|------|
| **RSI(14)** | Between 40 and 80 (not oversold, not extremely overbought) |
| **Volume** | Today's volume ≥ 70% of 20-day average (participation exists) |
| **52-week sweet spot** | Price 4–12% below 52-week high; 52w high not set in last 10 trading days |

**Why:** Filters out weak signals and low-volume noise.

---

### Stage 4 — Rank & Select

All ETFs passing Stages 1–3 are ranked by **momentum score**:

```
score = 0.4 × 12M return + 0.3 × 6M return + 0.2 × 3M return + 0.1 × 1M return
```

**Keep top 2** (highest momentum scores first).

---

## Trade Logic — Buy Order Setup

For each picked ETF:

1. **Buy trigger (LIMIT price)**
   - If 1M return ≥ 3M return → use live price
   - Else → use live price × 0.998 (pullback entry)
   - Apply **app safety floor**: must be above `(last EOD close − ₹0.06) + ₹0.01` on NSE

2. **Profit target** = trigger × 1.0314 (+3.14%)

3. **Quantity** = `max(1, floor(₹15,000 ÷ trigger))` whole units

4. **Amount** = qty × trigger (≈ ₹15,000 per slot)

---

## Output

**File:** `output/final_output_YYYYMMDD.csv`

**Columns:** `ticker`, `todays_last_price_inr`, `price_as_of`, `last_eod_close_inr`, `tomorrow_buy_trigger_inr`, `profit_target_inr`, `qty`, `amount_inr`, `note`

- Only ETFs that **pass all gates** (Stages 1–3)
- If none pass: `No ETFs to recommend at this time`
- Previous output files are cleaned up automatically

---

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Universe | 25 Indian ETFs | Fixed list in code |
| Benchmark | NIFTYBEES | For relative strength (Stage 2) |
| 55-day window | 55 trading days | Turtle breakout threshold |
| 20-day window | 20 trading days | Turtle exit zone |
| 12-month window | 252 trading days | Absolute momentum period |
| 3-month window | 63 trading days | Relative momentum period |
| RSI period | 14 | Standard momentum oscillator |
| Volume threshold | 70% | Of 20-day average |
| Profit target | 3.14% | Fixed per recommendation |

---

## Rationale

**Turtle Trading** + **Dual Momentum** combine:
- **Trend-following** (breakouts) — catches large moves
- **Momentum confirmation** — avoids false signals in sideways markets
- **Market context** (relative strength) — ignores sectors lagging the broad market
- **Volatility filters** (RSI, volume) — skips overextended or low-conviction moves

This is **short-term tactical**, suitable for swing traders or daily alert users.
