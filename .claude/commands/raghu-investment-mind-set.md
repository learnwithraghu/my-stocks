# Raghu's Investment Mindset — Reference for Building New Screeners

This skill defines how every new stock-picking method in this repo must be designed.
Always read and apply this before suggesting or building any new screener.

---

## The Core Rule: 2-3 Method Funnel, Never Just One

Every screener must combine **2 to 3 independent methods** into a sequential funnel.
A single method is never enough — convergent signals reduce false positives.

### Method Composition Law (non-negotiable)

| Slot | Type | Rule |
|------|------|------|
| 1 method | Traditional / Classic | Allowed. Must be well-established (e.g. Piotroski, Turtle, Dual Momentum, Moving Averages, RSI). Provides the foundation layer. |
| 1-2 methods | Modern — post-2021 only | Required. Must have been formally adopted or published by a named institutional firm (AQR, Two Sigma, Goldman Sachs QIS, Robeco, Coatue, Citadel, Man AHL, D.E. Shaw, etc.) after 2021. Must be traceable to a paper, fund disclosure, or published research. |

**You must never combine 2 traditional methods as the primary pair.** The modern method(s) must do real filtering work — not just cosmetic decoration.

### Why this matters
Traditional methods (Piotroski, Turtle, Momentum) are widely known. Edge comes from combining them with methods that most retail screeners do not use. The post-2021 requirement ensures the methods reflect current institutional thinking, not 1990s factor models.

---

## Funnel Design Rules

### Stage ordering
1. **Stage 1 — Cheapest signal first.** Price-based filters (200 DMA, 52-week high proximity, Turtle breakout) go first. They use only price history — fast, no expensive API calls.
2. **Stage 2 — Quality gate.** Fundamental signals (Piotroski, EGA, earnings growth) go second. They require fetching financials — run only on Stage 1 survivors.
3. **Stage 3 — Tiebreaker / final selector.** Momentum or scoring composite picks the top N winners from Stage 2 survivors.

### Output size
- Indian markets: **1 winner** (Piotroski screener) or **2 winners** (EGA screener)
- Never output a long list. High conviction, low count.

---

## Budget and Profit Rules by Market

| Market | Budget per trade | Transaction fee | Profit target | Shares |
|--------|-----------------|-----------------|---------------|--------|
| Indian (Nifty) | Rs 10,000 | none assumed | Rs 500 or 3.14%, whichever comes first | Whole shares only |
| Indian Midcap PEAD | Rs 10,000 | none assumed | Rs 500 or 3.14%, whichever comes first | Whole shares only |
| Indian ETF | Rs 10,000 | none assumed | Rs 500 or 3.14%, whichever comes first | Whole shares |

---

## Time Horizon Calibration

The methods chosen must match the intended holding period:

| Horizon | What to weight heavily | What to avoid |
|---------|----------------------|---------------|
| 2-3 weeks (short) | 52-week high proximity, 5-day momentum, volume surge, consolidation breakout | Multi-year fundamental trends, annual YoY comparisons as primary signal |
| 1-3 months (medium) | Piotroski F-Score, EGA, 12-1 month momentum, PEAD | Intraday patterns, RSI extremes |
| Long-term | Not in scope for this repo | — |

---

## Modern Methods Already Used (Do Not Repeat as "New")

These have already been implemented. Do not propose them as new:

| Method | Used in | Firm origin |
|--------|---------|-------------|
| 12-1 Month Momentum Tiebreaker | Nifty 200 Piotroski (Stage 3) | Academic / AQR |
| 200-Day MA Pre-filter | Nifty 200 Piotroski (Stage 1) | Winton / universal |
| Earnings Growth Acceleration (EGA) | Midcap+Smallcap screener (Stage 2) | Coatue / Goldman Sachs QIS 2023 |
| 52-Week High Proximity Momentum | Midcap+Smallcap screener (Stage 1) | Robeco 2022 |
| Post-Earnings Announcement Drift (PEAD) | Midcap PEAD screener (Stage 2) | Goldman Sachs QIS 2022, AQR |

---

## Strong Candidate Methods Not Yet Used (post-2021)

When proposing a new screener, prefer from this pool first:

| Method | Firms | Best for |
|--------|-------|---------|
| Short Interest as Value Trap Filter | D.E. Shaw, Two Sigma, Citadel (post-2021) | Quality confirmation; pair with Piotroski |
| Earnings Revision Score (ERS) | Goldman Sachs QIS 2021-2023, Nomura QIS | Forward-looking; pair with price momentum |
| Quality × Momentum Interaction Weighting | AQR 2022-2023, BlackRock SAE | Upgrading existing momentum scoring |
| ADX Trend Strength Filter | Man AHL, Winton Capital 2021-2023 | Replaces simple MA-above check |
| Mispricing Composite Score | BlackRock Systematic Equity 2022 | Multi-factor composite for ranking |

---

## What "New / Post-2021" Means — Checklist

Before accepting a method as valid for the "new" slot, verify all:
- [ ] The method was formally published, adopted, or disclosed by a named institutional firm after January 2021
- [ ] It is **not** a renamed version of an existing factor (e.g. "momentum" rebranded as "price trend" is still old)
- [ ] It can be implemented using data available from Yahoo Finance (yfinance) without paid data feeds
- [ ] It is **orthogonal** to the traditional method in the same screener — it must capture a different signal, not the same signal with a different formula

---

## Existing Screeners Reference

| Screener | Traditional method | Modern methods | Winners |
|----------|-------------------|----------------|---------|
| `indian-nifty100-analyzer-python` | Turtle Trading + Dual Momentum | — (upgrade candidate) | All passers |
| `indian-nifty200-piotroski` | Piotroski F-Score | 200 DMA pre-filter, 12-1M Momentum | 1 winner |
| `indian-midsmall-ega-screener` | RSI + Volume confirmation | EGA (Coatue/GS 2023), 52-Week High Proximity (Robeco 2022) | 2 winners |
| `indian-midcap-pead-screener` | 200 DMA + RSI + Volume | PEAD (GS QIS 2022 / AQR), 12-1M Momentum | 1 winner |
| `indian-etf-analyzer-python` | Turtle (20-day) + Dual Momentum | — (upgrade candidate) | All passers |

---

## Raghu's Style in One Paragraph

Raghu is a systematic investor who runs automated daily screeners across Indian markets. He favors quantitative funnel approaches — stacking 2-3 independent signals — over single-indicator systems. He insists on at least one method that reflects post-2021 institutional thinking so his edge does not come from widely-known, easily-arbitraged factors alone. He trades with fixed Rs 10,000 budgets per pick and targets Rs 500 total gain or 3.14%, whichever comes first. He needs methods that generate high-conviction, short-to-medium-term moves. He prefers 1-2 high-quality picks over a long list of mediocre ones. He has validated that tight pre-filters (200 DMA, 52-week high proximity, consolidation range) dramatically improve signal quality by eliminating structurally broken stocks before expensive fundamental checks run.
