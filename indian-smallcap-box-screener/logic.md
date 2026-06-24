# Smallcap Box Breakout Screener

Detects pump-style consolidation box breakouts on Nifty Smallcap 100 names under Rs 5,000 Cr market cap.

## Method Funnel

| Stage | Type | Signal |
|-------|------|--------|
| 1 | Traditional TA | 30-day box formation + fresh breakout today |
| 2 | Modern (Man AHL / Winton 2021–2023) | ADX trend emergence + volume spike |
| 3 | Rank | Composite `box_score` → 1 winner |

## Stage 1 — Box Formation + Breakout

Box defined on prior **30 trading days** (excluding today):

- `box_top` = max High in window
- `box_bottom` = min Low in window
- `box_width_pct` = (top − bottom) / midpoint × 100

**Pass when:**

- Box width between **8% and 22%**
- At least **15 of 30** closes inside the box
- Prior 5 sessions did not close above box top (fresh breakout)
- Today's price > box top
- Breakout extension ≤ **8%** above box top
- Market cap < **Rs 5,000 Cr**

## Stage 2 — ADX + Volume

- Average ADX(14) over box window < **25** (consolidation)
- Today +DI > −DI (bullish direction)
- Today ADX(14) > ADX(14) five sessions ago (trend waking)
- Today volume ≥ **2.0×** 20-day average (excluding today)

## Stage 3 — Ranking

```
box_score = 0.45 × volume_spike_ratio
          + 0.30 × (22 − box_width_pct) / 14
          + 0.25 × min(breakout_pct, 8) / 8
```

Tie-breakers: higher volume spike, then lower market cap.

## Sizing and Exits

| Field | Value |
|-------|-------|
| Budget | Rs 15,000 per pick |
| Profit target | min(+3.14%, Rs 500 total gain) |
| Stop loss | Box bottom (structural invalidation) |
| Winners | 1 per day |

## Risk Notes

- Pump-and-dump names can gap through the box bottom; the stop is informational, not a guaranteed fill.
- Yahoo volume for illiquid smallcaps can be noisy.
- No 52-week-high or 200-DMA filters — those would exclude most pump candidates.
