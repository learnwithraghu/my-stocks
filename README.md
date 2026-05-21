# my-stocks

Indian ETF screening with **Turtle trading** + **dual momentum**, local Python runner, and an agent skill for any index.

## Projects

| Path | Description |
|------|-------------|
| [`indian-etf-analyzer-python/`](indian-etf-analyzer-python/) | 25 Indian ETFs → `final_output_YYYYMMDD.csv` |
| [`indian-nifty100-analyzer-python/`](indian-nifty100-analyzer-python/) | Nifty 100 stocks, Turtle + Dual Momentum |
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
