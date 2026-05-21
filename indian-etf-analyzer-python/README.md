# Indian ETF Analyzer (Python)

## Setup & run

```bash
cd indian-etf-analyzer-python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python analyze_etfs.py
```

## Output (one file per day)

`output/final_output_YYYYMMDD.csv` — IST date, e.g. `final_output_20260521.csv`

- Only rows that **pass all recommendation gates**, with tomorrow order fields
- If none pass: one row with note `No ETFs to recommend at this time`
- Any other `.csv` in `output/` is deleted after each run

## CSV columns

| Column | Meaning |
|--------|---------|
| `ticker` | NSE symbol |
| `todays_last_price_inr` | Live / latest price (verify vs broker) |
| `price_as_of` | Date of live quote |
| `last_eod_close_inr` | Last completed daily close (Yahoo) |
| `tomorrow_buy_trigger_inr` | LIMIT (momentum + app safety floor applied) |
| `profit_target_inr` | Trigger + **3.14%** |
| `qty` | Units for ~₹15,000/trade |
| `amount_inr` | qty × trigger |
| `note` | `Passes all recommendation gates` |

## Budget

- Total: **₹3,00,000**
- Per trade: **₹15,000** (max **20** slots)

Not investment advice.
