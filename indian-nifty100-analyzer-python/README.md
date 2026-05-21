# Indian Nifty 100 Stock Analyzer

Screens **Nifty 100** NSE stocks using **Turtle trading + Dual Momentum** (see `.agent/turtle-dual-momentum/SKILL.md`).

## Strategy (all gates required)

| Layer | Rule |
|-------|------|
| **Turtle** | Live price ≥ 55-day high (excl. today); price > 20-day low |
| **Dual momentum** | 12M return > 0%; 3M return beats **NIFTYBEES** 3M |
| **Confirm** | RSI 14 between 40–80; volume ≥ 70% of 20-day avg |

## Run

```bash
cd indian-nifty100-analyzer-python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python analyze_stocks.py
```

**Runtime:** ~5–15 minutes (100 symbols × Yahoo requests).

## Output

`output/final_output_YYYYMMDD.csv` — same columns as the ETF analyzer:

`ticker`, `todays_last_price_inr`, `price_as_of`, `last_eod_close_inr`, `tomorrow_buy_trigger_inr`, `profit_target_inr`, `qty`, `amount_inr`, `note`

- Only stocks that **pass all gates**
- If none: one row with `No stocks to recommend at this time`
- Other CSVs in `output/` are deleted after each run

## Config

Edit top of `analyze_stocks.py`:

- `BUDGET_INR` = 300000  
- `TRADE_SIZE_INR` = 15000  
- `PROFIT_TARGET_PCT` = 3.14  
- `BENCHMARK` = NIFTYBEES (relative strength)

Edit universe in `nifty100_universe.py` (refresh from [Nifty 100 constituents](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-100) periodically).

## Disclaimer

Not investment advice. Yahoo prices may be delayed.
