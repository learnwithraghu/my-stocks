"""
Nifty Smallcap 100 NSE tickers — re-exported from midsmall universe.
Update the source list in indian-midsmall-ega-screener/midsmall_universe.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MIDSMALL = Path(__file__).resolve().parent.parent / "indian-midsmall-ega-screener"
if str(_MIDSMALL) not in sys.path:
    sys.path.insert(0, str(_MIDSMALL))

from midsmall_universe import NIFTY_SMALLCAP100_TICKERS

__all__ = ["NIFTY_SMALLCAP100_TICKERS"]
