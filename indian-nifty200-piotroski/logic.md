# Nifty 200 Piotroski F-Score Analyzer — Selection Logic

## Screener Overview

Selects from **Nifty 200 stocks** (200 NSE large & mid-caps) using a **three-stage funnel** combining trend health, fundamental strength, and momentum confirmation.

**Investment model:** ₹10,000 per winner (1 recommendation per day max).

**Horizon:** Weekly/swing trades (typically 1-3 weeks holding, fundamentals-driven).

---

## Stock Selection Method: Three-Stage Funnel

### Stage 1 — Trend Health Pre-Filter

**Gate:** Price > 200-day Moving Average

**Rule:** Live price must be above the 200-day simple moving average.

**Why:** Ensures you're buying in an uptrend, not catching falling knives. The 200-DMA is a classic long-term trend filter.

---

### Stage 2 — Piotroski F-Score (Fundamental Quality)

The **Piotroski F-Score** is a 9-point checklist measuring **year-over-year financial health**. Each criterion contributes 1 point:

| Metric | Positive (1 pt) | Negative (0 pts) |
|--------|-----------------|------------------|
| **Profitability** | Net Income > 0 | Net Income ≤ 0 |
| **Operating Cash Flow** | Operating CFO > 0 | Operating CFO ≤ 0 |
| **Quality of Earnings** | Operating CFO > Net Income | Operating CFO ≤ Net Income |
| **Leverage & Liquidity** | Debt (long-term) decreased YoY | Debt increased YoY |
| **Current Ratio** | Current Ratio increased YoY | Current Ratio decreased YoY |
| **Share Dilution** | Shares outstanding decreased | Shares increased (dilution) |
| **Gross Margin** | Gross Margin increased YoY | Gross Margin decreased |
| **Asset Turnover** | Asset Turnover increased YoY | Asset Turnover decreased |
| **ROA** | Return on Assets increased YoY | ROA decreased |

**Gate:** F-Score ≥ 7 (passes ≥7 of 9 checks)

**Why:** Filters for companies with improving fundamentals, not balance-sheet deterioration. Uses **true YoY comparisons**, not proxies.

---

### Stage 3 — Momentum Confirmation

**Gate:** 12-1 Month Price Momentum (highest wins)

**Rule:** Rank all survivors by 12-month-to-1-month price momentum composite. The **top 1 stock wins**.

**Calculation:**
```
momentum = 12M return (more recent weight) → decaying to → 1M return (current weight)
```

**Why:** Market confirmation — if fundamentals are improving, price should reflect it. Avoids boring value traps.

---

## Trade Logic — Buy Order Setup

For the 1 winner:

1. **Buy trigger (LIMIT price)**
   - Use live price (no pullback strategy at this horizon)
   - Apply **app safety floor**: must be above `(last EOD close − ₹0.06) + ₹0.01` on NSE

2. **Profit target** = whichever comes first: ₹500 total gain on the position or +3.14% from entry

3. **Quantity** = `₹10,000 ÷ entry price` (whole shares)

4. **Amount** = qty × entry price (≈ ₹10,000)

---

## Output

**File:** `output/final_output_YYYYMMDD.csv`

**Columns:** `date`, `ticker`, `company_name`, `current_price_inr`, `f_score`, `quantity`, `investment_inr`, `market_cap_cr`, `roe_pct`, `debt_to_equity`, `pe_ratio`, `pb_ratio`, `momentum_12_1_pct`, `above_200dma`, `note`, `profit_target_inr`

- 1 row: the top 1 momentum stock from all Stage 2 survivors
- If no stock passes Stage 1–2: `No stocks to recommend at this time`
- Previous output files are cleaned up automatically

---

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Universe | Nifty 200 stocks | 200 large & mid-cap NSE names |
| Stage 1 | Price > 200-DMA | Trend health filter |
| Stage 2 | F-Score ≥ 7 | Fundamental quality (9-pt checklist) |
| Stage 3 | Top 1 by momentum | 12-1 month composite momentum |
| 200-DMA window | 200 trading days | Long-term trend baseline |
| 12-month window | 252 trading days | Full-year momentum |
| 1-month window | ~21 trading days | Current momentum |
| Investment per winner | ₹10,000 | Fixed allocation |
| Profit target | ₹500 or 3.14% | Whichever comes first |

---

## Rationale

**Three-Stage Funnel** (Trend + Fundamentals + Momentum):
- **Stage 1 (Trend)** — avoids shorting or bottom-fishing
- **Stage 2 (Fundamentals)** — finds improving companies, not deteriorating balance sheets
- **Stage 3 (Momentum)** — confirms the market agrees; avoids "dead" value traps

This is **medium-term swing trading** (1-3 week horizon), suitable for:
- Fundamentals-focused investors who want market confirmation
- Traders seeking stocks with improving earnings
- Daily checkers looking for 1 quality recommendation per day

**Why Piotroski F-Score?**
- Measures **operational quality**, not just price
- 9-point checklist filters out deteriorating businesses
- YoY comparisons catch earnings momentum shifts
- Proven signal in academic research (Piotroski, 2000)

---

## Universe

Nifty 200 constituents are periodically refreshed from [NSE Nifty 200 official list](https://www.niftyindices.com/indices/equity/nifty-200). Edit `nifty200_universe.py` to update the ticker list.

---

## Sources

- Piotroski, J. D. (2000). "Value investing: The use of historical financial statement information to separate winners from losers." *Journal of Accounting Research*, 38(Supplement), 1–41.
