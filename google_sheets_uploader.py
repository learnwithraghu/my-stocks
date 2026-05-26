#!/usr/bin/env python3
"""
Google Sheets Uploader — writes daily screener results to a shared spreadsheet.
One sheet per strategy. Re-running the same date replaces existing rows (one batch per date).
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
    {
        "name": "nifty_midcap_PEAD_10k",
        "csv_path": "indian-midcap-pead-screener/output/midcap_winner.csv",
        "has_date_column": True,
        "date_column": "date",
    },
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def normalize_date(value: str) -> str:
    """Normalize to YYYY-MM-DD for row matching."""
    s = str(value).strip()
    if not s:
        return ""
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


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


def prepare_dataframe(df: pd.DataFrame, strategy: dict, run_date: str) -> pd.DataFrame:
    df = df.copy()
    if strategy.get("has_date_column") and strategy.get("date_column") not in df.columns:
        df[strategy["date_column"]] = run_date
    elif not strategy.get("has_date_column"):
        if "price_as_of" in df.columns:
            df["date"] = df["price_as_of"].iloc[0] if len(df) > 0 else run_date
        else:
            df["date"] = run_date
    return order_columns(df)


def order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Put date in the first column for every strategy."""
    if "date" not in df.columns:
        return df
    cols = ["date", *[c for c in df.columns if c != "date"]]
    return df[cols]


def canonical_headers(df: pd.DataFrame, existing: list[str]) -> list[str]:
    """Date first, then CSV columns, then any legacy sheet columns."""
    headers: list[str] = []
    for col in order_columns(df).columns:
        if col not in headers:
            headers.append(col)
    for col in existing:
        if col and col not in headers:
            headers.append(col)
    return headers


def ensure_headers(worksheet: gspread.Worksheet, df: pd.DataFrame) -> list[str]:
    existing = worksheet.row_values(1) if worksheet.row_count > 0 else []
    headers = canonical_headers(df, existing if existing and existing != [""] else [])

    if not existing or existing == [""]:
        worksheet.resize(rows=1, cols=len(headers))
        worksheet.insert_row(headers, index=1)
        return headers

    if len(headers) > worksheet.col_count:
        worksheet.resize(rows=worksheet.row_count, cols=len(headers))
    if headers != existing:
        worksheet.update(range_name="A1", values=[headers])
    return headers


def find_date_column_index(headers: list[str]) -> int | None:
    for name in ("date", "price_as_of"):
        if name in headers:
            return headers.index(name)
    return None


def delete_rows_for_date(worksheet: gspread.Worksheet, batch_date: str) -> int:
    """Remove existing rows matching batch_date (1-based sheet rows, header is row 1)."""
    values = worksheet.get_all_values()
    if len(values) < 2:
        return 0

    headers = values[0]
    date_idx = find_date_column_index(headers)
    if date_idx is None:
        return 0

    rows_to_delete: list[int] = []
    for row_num, row in enumerate(values[1:], start=2):
        if len(row) <= date_idx:
            continue
        if normalize_date(row[date_idx]) == batch_date:
            rows_to_delete.append(row_num)

    for row_num in sorted(rows_to_delete, reverse=True):
        worksheet.delete_rows(row_num)

    return len(rows_to_delete)


def row_to_values(row: pd.Series, headers: list[str]) -> list[str]:
    return [str(row.get(h, "")) if h in row.index else "" for h in headers]


def upsert_to_sheet(
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
        print(f"  {sheet_name}: No data to upload")
        return

    df = prepare_dataframe(df, strategy, run_date)
    batch_date = normalize_date(str(df["date"].iloc[0]))

    headers = ensure_headers(worksheet, df)
    removed = delete_rows_for_date(worksheet, batch_date)

    rows = [row_to_values(row, headers) for _, row in df.iterrows()]
    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")

    action = "Replaced" if removed else "Wrote"
    print(f"  {sheet_name}: {action} {len(rows)} row(s) for {batch_date} (removed {removed} old)")


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
        create_spreadsheet_if_needed(gc, sheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        return 1

    run_date = get_date_str()
    print(f"Uploading screener results for {run_date} to Google Sheet: {sheet_id}\n")

    for strategy in SHEET_STRATEGIES:
        try:
            upsert_to_sheet(gc, sheet_id, strategy, run_date)
        except Exception as e:
            print(f"  [error] Failed to upload {strategy['name']}: {e}", file=sys.stderr)
            continue

    print("\nUpload complete!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
