#!/usr/bin/env python3
"""Write minimal CSV fixtures for a fast Google Sheets upload smoke test."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = datetime.now(timezone.utc).strftime("%Y%m%d")
PRICE_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> None:
    print(f"Preparing upload test fixtures for {DATE}\n")

    write(
        ROOT / f"indian-etf-analyzer-python/output/final_output_{DATE}.csv",
        "ticker,todays_last_price_inr,price_as_of,last_eod_close_inr,tomorrow_buy_trigger_inr,"
        "profit_target_inr,qty,amount_inr,note\n"
        f"NIFTYBEES,100.0,{PRICE_DATE},100.0,100.0,103.14,50,5000,"
        "CI upload-test fixture\n",
    )
    write(
        ROOT / f"indian-nifty100-analyzer-python/output/final_output_{DATE}.csv",
        "ticker,todays_last_price_inr,price_as_of,last_eod_close_inr,tomorrow_buy_trigger_inr,"
        "profit_target_inr,qty,amount_inr,note\n"
        f"RELIANCE,100.0,{PRICE_DATE},100.0,100.0,103.14,10,1000,"
        "CI upload-test fixture\n",
    )
    write(
        ROOT / "indian-nifty200-piotroski/output/piotroski_winner.csv",
        "date,ticker,company_name,current_price_inr,f_score,quantity,investment_inr,"
        "market_cap_cr,roe_pct,debt_to_equity,pe_ratio,pb_ratio,momentum_12_1_pct,"
        "above_200dma,note\n"
        f"{PRICE_DATE},TESTCO,Test Company Limited,100.0,9,50,5000,1000.0,20.0,0.1,"
        "15.0,2.0,10.0,True,CI upload-test fixture\n",
    )
    write(
        ROOT / "indian-midsmall-ega-screener/output/ega_winners.csv",
        "date,ticker,company_name,current_price_inr,ega_score,quantity,investment_inr,note\n"
        f"{PRICE_DATE},TESTEGA,Test EGA Co,100.0,1.5,50,5000,CI upload-test fixture\n",
    )

    print("\nFixtures ready.")


if __name__ == "__main__":
    main()
