# US Stock Analyzer (Python)

Screens **S&P 100 style** US large-cap stocks using **Turtle trading + Dual Momentum** (see `.agent/turtle-dual-momentum/SKILL.md`).

## Strategy (all gates required)

| Layer | Rule |
|-------|------|
| **Turtle** | Live price ≥ 55-day high (excl. today); price > 20-day low |
| **Dual momentum** | 12M return > 0%; 3M return beats **SPY** 3M |
| **Confirm** | RSI 14 between 40–80; volume ≥ 70% of 20-day avg |
| **Budget** | Trigger ≤ **$50** (1 whole share must fit one-time budget) |

## Run

```bash
cd us-stock-analyzer-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python analyze_stocks.py
```

**Runtime:** ~5–15 minutes (~95 symbols × Yahoo requests).

## Output

`output/final_output_YYYYMMDD.csv` — same columns as the Indian analyzers (values are USD; column names kept for compatibility):

`ticker`, `todays_last_price_inr`, `price_as_of`, `last_eod_close_inr`, `tomorrow_buy_trigger_inr`, `profit_target_inr`, `qty`, `amount_inr`, `note`

- Top **1** stock that passes all gates and fits the **$50** budget
- If none: one row with `No stocks to recommend at this time`
- Other CSVs in `output/` are deleted after each run

## Config

Edit top of `analyze_stocks.py`:

- `BUDGET_USD` = 50 (one-time investment)
- `TRADE_SIZE_USD` = 50
- `MAX_SLOTS` = 1
- `PROFIT_TARGET_PCT` = 3.14
- `BENCHMARK` = SPY (relative strength)

Edit universe in `us_universe.py` (refresh from [S&P 100 constituents](https://www.spglobal.com/spdji/en/indices/equity/sp-100/) periodically).

## Disclaimer

Not investment advice. Yahoo prices may be delayed.
