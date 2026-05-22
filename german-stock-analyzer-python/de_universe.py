"""
Top 50 German large-cap stocks — DAX 40 + 10 MDAX leaders (XETRA).
Update periodically from DAX / MDAX constituent lists.
"""

GERMAN_STOCK_TICKERS = [
    # DAX 40
    "ADS", "AIR", "ALV", "BAS", "BAYN", "BEI", "BMW", "BNR", "CBK", "CON",
    "DBK", "DHL", "DTE", "DTG", "ENR", "EOAN", "FME", "FRE", "HEI", "HEN3",
    "HNR1", "IFX", "MBG", "MRK", "MTX", "MUV2", "PAH3", "P911", "QIA", "RHM",
    "RWE", "SAP", "SHL", "SIE", "SRT3", "SY1", "VNA", "VOW3", "ZAL", "G1A",
    # MDAX leaders (top 10 by index weight)
    "EVK", "HOT", "LEG", "PUM", "FRA", "WCH", "HFG", "HAG", "NDX1", "TLX",
]

GERMAN_STOCK_TICKERS = sorted(set(GERMAN_STOCK_TICKERS))[:50]
