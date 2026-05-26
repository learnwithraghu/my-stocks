#!/usr/bin/env python3
"""
Google Sheets Uploader — appends daily screener results to a shared spreadsheet.
One sheet per strategy; each run adds a new row with the date and results.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd
from google.auth import exceptions as google_exceptions
from google.oauth2.service_account import Credentials

SHEET_STRATEGIES = [
    {
        "name": "indian_etf",
        "csv_path": "indian-etf-analyzer-python/output/final_output_{date}.csv",
        "has_date_column": False,
    },
    {
        "name": "nifty100",
        "csv_path": "indian-nifty100-analyzer-python/output/final_output_{date}.csv",
        "has_date_column": False,
    },
    {
        "name": "us_stocks",
        "csv_path": "us-stock-analyzer-python/output/final_output_{date}.csv",
        "has_date_column": False,
    },
    {
        "name": "german_stocks",
        "csv_path": "german-stock-analyzer-python/output/final_output_{date}.csv",
        "has_date_column": False,
    },
    {
        "name": "piotroski",
        "csv_path": "indian-nifty200-piotroski/output/piotroski_winner.csv",
        "has_date_column": True,
        "date_column": "date",
    },
    {
        "name": "ega_screener",
        "csv_path": "indian-midsmall-ega-screener/output/ega_winners.csv",
        "has_date_column": True,
        "date_column": "date",
    },
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def get_creds() -> Credentials:
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not creds_json:
        raise ValueError("GOOGLE_SHEETS_CREDENTIALS environment variable not set")

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return creds


def get_gc() -> gspread.Client:
    creds = get_creds()
    return gspread.authorize(creds)


def get_or_create_sheet(spreadsheet, sheet_name: str) -> gspread.Worksheet:
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1, cols=1)
    return worksheet


def ensure_header(worksheet: gspread.Worksheet, headers: list[str]) -> None:
    existing = worksheet.row_values(1)
    if not existing or existing == [""]:
        worksheet.insert_row(headers, index=1)
    else:
        current_headers = existing
        for i, h in enumerate(headers):
            if h not in current_headers:
                current_headers.append(h)
        if current_headers != existing:
            worksheet.resize(rows=1, cols=len(current_headers))
            worksheet.insert_row(current_headers, index=1)


def read_csv_safe(csv_path: Path) -> pd.DataFrame | None:
    if not csv_path.exists():
        print(f"  [warn] CSV not found: {csv_path}")
        return None
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        print(f"  [error] Failed to read {csv_path}: {e}")
        return None


def append_to_sheet(
    gc: gspread.Client,
    sheet_id: str,
    strategy: dict,
    run_date: str,
) -> None:
    csv_path = Path(strategy["csv_path"].format(date=run_date))
    df = read_csv_safe(csv_path)

    spreadsheet = gc.open_by_key(sheet_id)
    sheet_name = strategy["name"]
    worksheet = get_or_create_sheet(spreadsheet, sheet_name)

    if df is None or df.empty:
        print(f"  {sheet_name}: No data to append")
        return

    if strategy.get("has_date_column") and strategy.get("date_column") not in df.columns:
        df[strategy["date_column"]] = run_date
    elif not strategy.get("has_date_column"):
        if "price_as_of" in df.columns:
            df["date"] = df["price_as_of"].iloc[0] if len(df) > 0 else run_date
        else:
            df["date"] = run_date

    headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
    if not headers or headers == [""]:
        headers = list(df.columns)
        worksheet.resize(rows=1, cols=len(headers))
        worksheet.insert_row(headers, index=1)

    all_headers = headers + [h for h in df.columns if h not in headers]
    if len(all_headers) > worksheet.col_count:
        worksheet.resize(rows=worksheet.row_count, cols=len(all_headers))

    for _, row in df.iterrows():
        row_data = []
        for h in all_headers:
            row_data.append(str(row.get(h, "")) if h in row.index else "")
        worksheet.append_row(row_data, value_input_option="USER_ENTERED")

    print(f"  {sheet_name}: Appended {len(df)} row(s)")


def create_spreadsheet_if_needed(gc: gspread.Client, sheet_id: str) -> gspread.Spreadsheet:
    try:
        return gc.open_by_key(sheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Spreadsheet {sheet_id} not found. Please create one and share it with the service account.")
        raise


def main() -> int:
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("ERROR: GOOGLE_SHEET_ID environment variable not set", file=sys.stderr)
        return 1

    try:
        gc = get_gc()
    except (ValueError, google_exceptions.GoogleAuthError) as e:
        print(f"ERROR: Failed to authenticate with Google Sheets: {e}", file=sys.stderr)
        return 1

    try:
        spreadsheet = create_spreadsheet_if_needed(gc, sheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        return 1

    run_date = get_date_str()
    print(f"Uploading screener results for {run_date} to Google Sheet: {sheet_id}\n")

    for strategy in SHEET_STRATEGIES:
        try:
            append_to_sheet(gc, sheet_id, strategy, run_date)
        except Exception as e:
            print(f"  [error] Failed to upload {strategy['name']}: {e}", file=sys.stderr)
            continue

    print("\nUpload complete!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())