# Nifty Midcap 100 PEAD Daily Winner — Selection Logic

## Screener Overview

Selects **1 winner** from **Nifty Midcap 100** using a three-stage funnel:

| Layer | Method | Origin |
|-------|--------|--------|
| Stage 1 | 200 DMA + RSI + volume | Traditional trend/liquidity |
| Stage 2 | **Post-Earnings Announcement Drift (PEAD)** | Goldman Sachs QIS 2022, AQR systematic equity |
| Stage 3 | 12-1 month momentum rank | Tiebreaker (Piotroski-style) |

**Investment:** ₹10,000 per winner (whole shares).  
**Horizon:** 2–6 weeks (post-earnings drift).

Runs **alongside** `indian-midsmall-ega-screener` (different universe, signal, and budget).

---

## Stage 1 — Traditional pre-filter (fast)

| Gate | Rule |
|------|------|
| 200 DMA | Close > SMA(200) |
| RSI(14) | 45–75 |
| Volume | Today ≥ 70% of 20-day average |

---

## Stage 2 — PEAD gate (modern)

### Earnings recency

Last report within **30 calendar days** (`earnings_dates` index, or calendar fallback).

### Earnings surprise (first match wins)

| Priority | Source | Pass rule |
|----------|--------|-----------|
| 1 | `earnings_dates` (EPS actual vs estimate, or Surprise %) | Surprise ≥ **3%** |
| 2 | Quarterly financials QoQ net income | Jump ≥ **8%** |
| 3 | `info.earningsQuarterlyGrowth` | ≥ **10%** and report within 30 days |

### Drift confirmation

- Within **15%** of 52-week high  
- **5-day return ≥ 0%**

Stocks failing all paths are dropped. **No filler winner.**

---

## Stage 3 — Single winner

```
pead_rank_score = 0.50 × surprise_pct + 0.50 × momentum_12_1_pct
```

Pick **highest** `pead_rank_score`. Tie-break: higher `surprise_pct`, then higher `market_cap_cr`.

---

## Output

**File:** `output/midcap_winner.csv`

**Columns:** `date`, `ticker`, `company_name`, `current_price_inr`, `quantity`, `investment_inr`, `surprise_pct`, `earnings_days_ago`, `momentum_12_1_pct`, `above_200dma`, `rsi_14`, `gap_to_52wh_pct`, `pe_ratio`, `market_cap_cr`, `pead_rank_score`, `note`

If no winner: one row, `note` = `No stocks to recommend at this time`.

---

## Key parameters

| Parameter | Value |
|-----------|-------|
| Universe | Nifty Midcap 100 |
| Investment | ₹10,000 |
| Max winners | 1 |
| Earnings window | 30 days |
| Min surprise (estimate) | 3% |
| Min surprise (QoQ) | 8% |
| Min surprise (info) | 10% |
| Max 52-week gap | 15% |

---

## Sources

- Piotroski-style 12-1 momentum: academic / AQR  
- PEAD: Bernard & Thomas; systematic equity desks (GS QIS 2022, AQR)  
- Universe: [Nifty Midcap 100](https://www.niftyindices.com/indices/equity/nifty-midcap-100)
