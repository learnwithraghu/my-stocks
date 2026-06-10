#!/usr/bin/env python3
"""
Dry-run comparison: current screener picks vs proposed anti-overextension filter.

Proposed filter (comparison only — does NOT write production CSVs):
  - price > 200-DMA
  - 5% <= gap_to_52w_high_pct <= 10% (via passes_52w_sweet_spot)

Usage:
  python compare_momentum_filter.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filters_52w import (
    BAND_STOCK,
    above_200dma,
    gap_to_52w_high_pct,
    high_52w_from_history,
    passes_52w_sweet_spot,
)

# Comparison band matches production stock filter
BAND_PROPOSED = BAND_STOCK

# ── import analyzer modules ──────────────────────────────────────────────────

sys.path.insert(0, str(ROOT / "indian-etf-analyzer-python"))
import analyze_etfs as etf_mod  # noqa: E402

sys.path.insert(0, str(ROOT / "indian-nifty200-piotroski"))
import analyze_piotroski as piot_mod  # noqa: E402
from nifty200_universe import NIFTY200_TICKERS  # noqa: E402

sys.path.insert(0, str(ROOT / "indian-midsmall-ega-screener"))
import analyze_stocks as ega_mod  # noqa: E402
from midsmall_universe import MIDSMALL_TICKERS  # noqa: E402

sys.path.insert(0, str(ROOT / "indian-midcap-pead-screener"))
import analyze_pead as pead_mod  # noqa: E402
from midcap100_universe import NIFTY_MIDCAP100_TICKERS  # noqa: E402


@dataclass
class PickMetrics:
    ticker: str
    price: float | None
    above_200dma: bool | None
    gap_to_52wh_pct: float | None
    passes_proposed: bool
    proposed_reason: str
    extra: str = ""


def proposed_filter(hist: pd.DataFrame, price: float) -> tuple[bool, float | None, bool | None, str]:
    """Returns (passes, gap_pct, above_200dma, reason)."""
    dma_ok = above_200dma(hist, price)
    if dma_ok is None:
        return False, None, None, "insufficient history for 200-DMA"
    if not dma_ok:
        gap = None
        high_52w = high_52w_from_history(hist)
        if high_52w and price > 0:
            gap = gap_to_52w_high_pct(high_52w, price)
        return False, gap, False, "below 200-DMA"

    passes, gap_pct, reason = passes_52w_sweet_spot(hist, price, *BAND_PROPOSED)
    if not passes:
        return False, gap_pct, True, reason
    return True, gap_pct, True, "ok"


def fmt_pick(m: PickMetrics | None) -> str:
    if m is None:
        return "No pick"
    dma = "Y" if m.above_200dma else ("N" if m.above_200dma is False else "?")
    gap = f"{m.gap_to_52wh_pct:.1f}%" if m.gap_to_52wh_pct is not None else "N/A"
    flag = "PASS" if m.passes_proposed else f"FAIL ({m.proposed_reason})"
    extra = f" | {m.extra}" if m.extra else ""
    price = f"₹{m.price:.2f}" if m.price is not None else "N/A"
    return f"{m.ticker} @ {price} | 200-DMA:{dma} | gap:{gap} | proposed:{flag}{extra}"


def metrics_from_hist(ticker: str, hist: pd.DataFrame, price: float, extra: str = "") -> PickMetrics:
    ok, gap, dma, reason = proposed_filter(hist, price)
    return PickMetrics(ticker, price, dma, gap, ok, reason, extra)


# ── ETF ──────────────────────────────────────────────────────────────────────

def run_etf_comparison() -> dict:
    print("\n" + "=" * 72)
    print("ETF TURTLE / DUAL MOMENTUM")
    print("=" * 72)

    nb = etf_mod.fetch_history("NIFTYBEES")
    nifty_3m = (
        etf_mod.trading_return(nb["Close"], etf_mod.MOM_3M)
        if nb is not None and len(nb["Close"]) > etf_mod.MOM_3M
        else None
    )

    metrics = [etf_mod.analyze_one(etf, nifty_3m) for etf in etf_mod.ETF_UNIVERSE]
    current_picks = sorted(
        [m for m in metrics if m.recommended and m.score is not None],
        key=lambda x: x.score,
        reverse=True,
    )[: etf_mod.MAX_SLOTS]

    # Proposed: same gates + proposed filter
    proposed_candidates = []
    for m in metrics:
        if not m.recommended or m.score is None or m.price is None:
            continue
        df = etf_mod.fetch_history(m.ticker)
        if df is None:
            continue
        ok, _, _, _ = proposed_filter(df, m.price)
        if ok:
            proposed_candidates.append(m)
    proposed_picks = sorted(proposed_candidates, key=lambda x: x.score, reverse=True)[
        : etf_mod.MAX_SLOTS
    ]

    current_metrics = []
    for m in current_picks:
        df = etf_mod.fetch_history(m.ticker)
        pm = metrics_from_hist(
            m.ticker,
            df,
            m.price,
            extra=f"score={m.score:.2f} current_band={etf_mod.BAND_TURTLE_DM}",
        ) if df is not None else PickMetrics(m.ticker, m.price, None, m.gap_to_52wh_pct, False, "no history")
        current_metrics.append(pm)

    proposed_metrics = []
    for m in proposed_picks:
        df = etf_mod.fetch_history(m.ticker)
        pm = metrics_from_hist(m.ticker, df, m.price, extra=f"score={m.score:.2f}") if df is not None else None
        if pm:
            proposed_metrics.append(pm)

    total_rec = sum(1 for m in metrics if m.recommended)
    total_proposed = len(proposed_candidates)

    print(f"Current band: {etf_mod.BAND_TURTLE_DM[0]}-{etf_mod.BAND_TURTLE_DM[1]}% below 52w high (no explicit 200-DMA gate)")
    print(f"Proposed band: {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52w high + price > 200-DMA")
    print(f"Candidates: current={total_rec} recommended -> proposed={total_proposed} pass new filter")
    print("\nCurrent pick(s):")
    for pm in current_metrics:
        print(f"  {fmt_pick(pm)}")
    if not current_metrics:
        print("  No pick")
    print("\nProposed-filter pick(s):")
    for pm in proposed_metrics:
        print(f"  {fmt_pick(pm)}")
    if not proposed_metrics:
        print("  No pick")

    return {
        "method": "ETF",
        "current": current_metrics,
        "proposed": proposed_metrics,
        "current_count": len(current_picks),
        "proposed_count": len(proposed_picks),
    }


# ── Piotroski ─────────────────────────────────────────────────────────────────

def run_piotroski_comparison() -> dict:
    print("\n" + "=" * 72)
    print("NIFTY 200 PIOTROSKI")
    print("=" * 72)

    stage1: list[tuple[str, pd.DataFrame]] = []
    for ticker in NIFTY200_TICKERS:
        hist = piot_mod.fetch_price_history(ticker)
        if hist is None:
            continue
        if piot_mod.passes_200dma_filter(hist) and piot_mod.passes_20dma_filter(hist):
            stage1.append((ticker, hist))

    candidates: list[piot_mod.StockResult] = []
    for ticker, hist in stage1:
        result = piot_mod.analyze_stock(ticker, hist)
        if result:
            candidates.append(result)

    def rank_candidates(pool: list[piot_mod.StockResult]) -> list[piot_mod.StockResult]:
        with_mom = [c for c in pool if c.momentum_12_1_pct is not None]
        if with_mom:
            positive = [c for c in with_mom if c.momentum_12_1_pct > 0]
            use = positive if positive else with_mom
            return sorted(use, key=lambda x: x.momentum_12_1_pct, reverse=True)
        return sorted(pool, key=lambda x: (x.f_score, x.market_cap_cr or 0), reverse=True)

    ranked = rank_candidates(candidates)
    current_winner = ranked[0] if ranked else None

    # Proposed: filter candidates by 52w sweet spot (already above 200-DMA from stage1)
    proposed_pool: list[piot_mod.StockResult] = []
    for c in candidates:
        hist = next(h for t, h in stage1 if t == c.ticker)
        ok, _, _, _ = proposed_filter(hist, c.current_price_inr)
        if ok:
            proposed_pool.append(c)
    proposed_ranked = rank_candidates(proposed_pool)
    proposed_winner = proposed_ranked[0] if proposed_ranked else None

    def to_metrics(w: piot_mod.StockResult | None) -> PickMetrics | None:
        if w is None:
            return None
        hist = next(h for t, h in stage1 if t == w.ticker)
        mom = f"F={w.f_score}/9 mom={w.momentum_12_1_pct:+.1f}%" if w.momentum_12_1_pct is not None else f"F={w.f_score}/9"
        return metrics_from_hist(w.ticker, hist, w.current_price_inr, extra=mom)

    cur_m = to_metrics(current_winner)
    prop_m = to_metrics(proposed_winner)

    print("Current: price > 200-DMA + 20-DMA, F>=7, highest 12-1M momentum (no 52w gap gate)")
    print(f"Proposed: add {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52w high")
    print(f"Candidates: stage1={len(stage1)} -> F>=7={len(candidates)} -> proposed={len(proposed_pool)}")
    print(f"\nCurrent winner: {fmt_pick(cur_m)}")
    print(f"Proposed winner: {fmt_pick(prop_m)}")

    return {
        "method": "Piotroski",
        "current": [cur_m] if cur_m else [],
        "proposed": [prop_m] if prop_m else [],
        "current_count": 1 if current_winner else 0,
        "proposed_count": 1 if proposed_winner else 0,
    }


# ── EGA ───────────────────────────────────────────────────────────────────────

def run_ega_comparison() -> dict:
    print("\n" + "=" * 72)
    print("MID/SMALL EGA")
    print("=" * 72)

    stage1: list[tuple[str, pd.DataFrame, dict]] = []
    for ticker in MIDSMALL_TICKERS:
        try:
            stock = yf.Ticker(ega_mod.yahoo_symbol(ticker))
            info = stock.info or {}
            if not info:
                continue
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 20:
                continue
            passes, gap_pct, mom_5d = ega_mod.passes_proximity_filter(info, hist)
            if passes:
                stage1.append((ticker, hist, info))
        except Exception:
            continue

    candidates: list[ega_mod.StockResult] = []
    for ticker, hist, info in stage1:
        result = ega_mod.analyze_stock(ticker, hist, info)
        if result:
            candidates.append(result)

    candidates.sort(key=lambda x: x.ega_score, reverse=True)
    current_winners = candidates[: ega_mod.TOP_N]

    proposed_candidates: list[ega_mod.StockResult] = []
    for c in candidates:
        hist = next(h for t, h, _ in stage1 if t == c.ticker)
        ok, _, _, _ = proposed_filter(hist, c.current_price_inr)
        if ok:
            proposed_candidates.append(c)
    proposed_candidates.sort(key=lambda x: x.ega_score, reverse=True)
    proposed_winners = proposed_candidates[: ega_mod.TOP_N]

    def to_metrics(w: ega_mod.StockResult) -> PickMetrics:
        hist = next(h for t, h, _ in stage1 if t == w.ticker)
        return metrics_from_hist(
            w.ticker,
            hist,
            w.current_price_inr,
            extra=f"EGA={w.ega_score:.2f} gap_current={w.gap_to_52wh_pct:.1f}%",
        )

    cur_ms = [to_metrics(w) for w in current_winners]
    prop_ms = [to_metrics(w) for w in proposed_winners]

    print(f"Current band: {ega_mod.BAND_EGA[0]}-{ega_mod.BAND_EGA[1]}% below 52w high (no explicit 200-DMA gate)")
    print(f"Proposed band: {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52w high + price > 200-DMA")
    print(f"Candidates: stage1={len(stage1)} -> EGA qualified={len(candidates)} -> proposed={len(proposed_candidates)}")
    print("\nCurrent winner(s):")
    for pm in cur_ms:
        print(f"  {fmt_pick(pm)}")
    if not cur_ms:
        print("  No pick")
    print("\nProposed-filter winner(s):")
    for pm in prop_ms:
        print(f"  {fmt_pick(pm)}")
    if not prop_ms:
        print("  No pick")

    return {
        "method": "EGA",
        "current": cur_ms,
        "proposed": prop_ms,
        "current_count": len(current_winners),
        "proposed_count": len(proposed_winners),
    }


# ── PEAD ──────────────────────────────────────────────────────────────────────

def run_pead_comparison() -> dict:
    print("\n" + "=" * 72)
    print("MIDCAP PEAD")
    print("=" * 72)

    now = datetime.now(timezone.utc)
    stage1: list[tuple[str, pd.DataFrame, float]] = []
    for ticker in NIFTY_MIDCAP100_TICKERS:
        hist = pead_mod.fetch_price_history(ticker)
        if hist is None:
            continue
        ok, rsi = pead_mod.passes_stage1(hist)
        if ok:
            stage1.append((ticker, hist, rsi))

    candidates: list[pead_mod.StockResult] = []
    for ticker, hist, rsi in stage1:
        result = pead_mod.analyze_stock(ticker, hist, rsi, now)
        if result:
            candidates.append(result)

    current_winner = pead_mod.pick_winner(candidates)

    proposed_pool: list[pead_mod.StockResult] = []
    for c in candidates:
        hist = next(h for t, h, _ in stage1 if t == c.ticker)
        ok, _, _, _ = proposed_filter(hist, c.current_price_inr)
        if ok:
            proposed_pool.append(c)
    proposed_winner = pead_mod.pick_winner(proposed_pool)

    def to_metrics(w: pead_mod.StockResult | None) -> PickMetrics | None:
        if w is None:
            return None
        hist = next(h for t, h, _ in stage1 if t == w.ticker)
        return metrics_from_hist(
            w.ticker,
            hist,
            w.current_price_inr,
            extra=f"surprise={w.surprise_pct:+.1f}% gap_current={w.gap_to_52wh_pct:.1f}%",
        )

    cur_m = to_metrics(current_winner)
    prop_m = to_metrics(proposed_winner)

    print("Current: price > 200-DMA, PEAD surprise, drift <= 15% below 52w high")
    print(f"Proposed: tighten drift to {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52w high")
    print(f"Candidates: stage1={len(stage1)} -> PEAD={len(candidates)} -> proposed={len(proposed_pool)}")
    print(f"\nCurrent winner: {fmt_pick(cur_m)}")
    print(f"Proposed winner: {fmt_pick(prop_m)}")

    return {
        "method": "PEAD",
        "current": [cur_m] if cur_m else [],
        "proposed": [prop_m] if prop_m else [],
        "current_count": 1 if current_winner else 0,
        "proposed_count": 1 if proposed_winner else 0,
    }


def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    run_at = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    print(f"Run: {run_at}")
    print(f"Proposed filter: price > 200-DMA AND {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52-week high")
    print("(Dry run only — production CSVs were NOT modified.)\n")

    for r in results:
        method = r["method"]
        current = r["current"]
        proposed = r["proposed"]
        print(f"--- {method} ---")
        cur_tickers = [p.ticker for p in current if p]
        prop_tickers = [p.ticker for p in proposed if p]
        print(f"  Current pick(s):  {', '.join(cur_tickers) or 'none'}")
        print(f"  Proposed pick(s): {', '.join(prop_tickers) or 'none'}")

        for pm in current:
            if pm is None:
                continue
            status = "already passes proposed filter" if pm.passes_proposed else f"FAILS proposed ({pm.proposed_reason})"
            print(f"  {pm.ticker} (current): {status}")

        changed = cur_tickers != prop_tickers
        print(f"  Pick changed: {'YES' if changed else 'NO'}")
        print(f"  Candidate pool shrink: current winners from {r['current_count']} slot(s), proposed {r['proposed_count']} slot(s)")
        print()


def main() -> int:
    print("Momentum Filter Dry-Run Comparison")
    print("=" * 72)
    print(
        "Evaluating whether a stricter anti-overextension filter improves pick quality.\n"
        f"Proposed: price > 200-DMA AND {BAND_PROPOSED[0]}-{BAND_PROPOSED[1]}% below 52-week high."
    )

    results = [
        run_etf_comparison(),
        run_piotroski_comparison(),
        run_ega_comparison(),
        run_pead_comparison(),
    ]
    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
