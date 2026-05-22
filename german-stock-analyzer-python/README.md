# German Stock Analyzer (Python)

Screens **top 50** German large-cap stocks (DAX 40 + MDAX leaders) using **Turtle trading + Dual Momentum** (see `.agent/turtle-dual-momentum/SKILL.md`).

## Strategy (all gates required)

| Layer | Rule |
|-------|------|
| **Turtle** | Live price ≥ 55-day high (excl. today); price > 20-day low |
| **Dual momentum** | 12M return > 0%; 3M return beats **EXS1** (DAX ETF) 3M |
| **Confirm** | RSI 14 between 40–80; volume ≥ 70% of 20-day avg |
| **Budget** | Trigger ≤ **$50 USD** (1 whole share; EUR XETRA price converted via EUR/USD) |

## Run

```bash
cd german-stock-analyzer-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python analyze_stocks.py
```

**Runtime:** ~3–8 minutes (50 symbols × Yahoo requests).

## Output

`output/final_output_YYYYMMDD.csv` — same columns as the US analyzer (values are **USD**; column names kept for compatibility):

`ticker`, `todays_last_price_inr`, `price_as_of`, `last_eod_close_inr`, `tomorrow_buy_trigger_inr`, `profit_target_inr`, `qty`, `amount_inr`, `note`

- Top **1** stock that passes all gates and fits the **$50** budget
- If none: one row with `No stocks to recommend at this time`
- Other CSVs in `output/` are deleted after each run

## Config

Edit top of `analyze_stocks.py`:

- `BUDGET_USD` = 50 (one-time investment, same as US stock)
- `TRADE_SIZE_USD` = 50
- `MAX_SLOTS` = 1
- `PROFIT_TARGET_PCT` = 3.14
- `BENCHMARK` = EXS1 (iShares Core DAX ETF, XETRA)

Edit universe in `de_universe.py` (refresh from [DAX](https://www.dax-indices.com/) / [MDAX](https://www.dax-indices.com/) constituents periodically).

## Disclaimer

Not investment advice. Yahoo prices may be delayed.
