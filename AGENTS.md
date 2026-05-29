# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

This repo contains Python stock and ETF screeners for Indian markets. The main data source is Yahoo Finance through `yfinance`, and daily results are uploaded to Google Sheets by `google_sheets_uploader.py`.

Primary projects:

- `indian-etf-analyzer-python/`: Indian ETF Turtle/Dual Momentum screener, top 2 picks at Rs 10,000 each.
- `indian-nifty100-analyzer-python/`: Nifty 100 Turtle/Dual Momentum screener, top 2 picks at Rs 10,000 each.
- `indian-nifty200-piotroski/`: Nifty 200 Piotroski F-Score screener, 1 winner at Rs 10,000.
- `indian-midsmall-ega-screener/`: Midcap/Smallcap Earnings Growth Acceleration screener, 2 winners at Rs 10,000 each.
- `indian-midcap-pead-screener/`: Nifty Midcap 100 PEAD screener, 1 winner at Rs 10,000.
- `.agent/turtle-dual-momentum/`: Agent skill and generic runner for Turtle/Dual Momentum strategies.

## Runtime And Dependencies

- Use Python 3.11, matching `.github/workflows/daily-screener.yml`.
- Install root Google Sheets dependencies with `pip install -r requirements-google-sheets.txt`.
- Install analyzer-specific dependencies from each analyzer folder's `requirements.txt` when running that analyzer locally.
- Most screeners make many Yahoo Finance requests and can take several minutes.

## Running Screeners

From the repo root:

```bash
python indian-etf-analyzer-python/analyze_etfs.py
python indian-nifty100-analyzer-python/analyze_stocks.py
python indian-nifty200-piotroski/analyze_piotroski.py
python indian-midsmall-ega-screener/analyze_stocks.py
python indian-midcap-pead-screener/analyze_pead.py
```

The GitHub Action runs these on weekdays at 18:30 Dubai time / 20:00 IST:

```yaml
cron: "30 14 * * 1-5"
```

GitHub Actions cron uses UTC.

## Output Conventions

- Analyzer outputs are written under each analyzer's `output/` directory.
- Turtle/Dual Momentum analyzers write `output/final_output_YYYYMMDD.csv`.
- Other analyzers write fixed CSVs such as `piotroski_winner.csv`, `ega_winners.csv`, and `midcap_winner.csv`.
- Generated output CSVs are artifacts, not source. Do not commit them unless the user explicitly asks.
- If no symbol passes filters, scripts usually emit a single "No stocks to recommend at this time" row.
- Every method uses Rs 10,000 per selected pick.
- Profit targets use the first/lower target between Rs 500 total gain on the position and +3.14% from entry.
- When adding new Google Sheets columns, append them to `OUTPUT_COLUMNS` so existing sheet data does not shift under different headers.

## Google Sheets Uploads

- `google_sheets_uploader.py` reads the analyzer output CSVs and upserts rows by date.
- Required environment variables are `GOOGLE_SHEETS_CREDENTIALS` and `GOOGLE_SHEET_ID`.
- Never print, commit, or hardcode Google credentials or sheet IDs.
- The workflow uploads artifacts even if individual screeners fail, because analyzer steps use `continue-on-error: true`.

## Coding Guidelines

- Preserve the existing simple script style: standard library, `pandas`, `yfinance`, and small helper functions.
- Keep strategy constants near the top of each analyzer script.
- Use `.NS` Yahoo Finance symbols for NSE tickers through local `yahoo_symbol()` helpers.
- Shared 52-week high filters live in `filters_52w.py`; reuse them rather than duplicating that logic.
- Keep investment sizing and profit target constants consistent across methods unless the user asks for method-specific values.
- Universe membership is defined in each `*_universe.py` file. Update those lists carefully and keep ticker strings plain.
- Date-sensitive screener outputs use IST (`Asia/Kolkata`) unless a file already documents otherwise.

## Validation

For narrow changes, run the touched script if practical. For workflow-only or docs-only changes, at minimum inspect the YAML or Markdown diff.

Useful checks:

```bash
python -m py_compile google_sheets_uploader.py filters_52w.py
python indian-etf-analyzer-python/analyze_etfs.py
```

Some validations require network access and can be slow because Yahoo Finance is queried live.

## Git Hygiene

- Commit only files relevant to the user request.
- Leave local planning files such as `.kilo/` alone unless the user explicitly asks to include them.
- Avoid unrelated rewrites of generated output, large CSV artifacts, or strategy parameters.
