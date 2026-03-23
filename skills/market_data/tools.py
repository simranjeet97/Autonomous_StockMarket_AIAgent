"""
tools/market_data_tools.py
───────────────────────────
Observer-only tools for fetching live and historical market data.
These tools NEVER place orders — they are safe for the Analyst Agent.

Primary source: yfinance (NSE suffix: .NS)
Production: swap to Dhan / Zerodha market data API.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import yfinance as yf

    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False
    logger.warning("yfinance not installed — market data will return stubs")


def _nse_ticker(symbol: str) -> str:
    """Convert bare symbol to yfinance NSE format (e.g. RELIANCE → RELIANCE.NS)."""
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.startswith("^"):
        return f"{symbol}.NS"
    return symbol


def get_ltp(symbol: str) -> dict:
    """
    Get the Last Traded Price (LTP) for an NSE symbol.

    Args:
        symbol: NSE ticker, e.g. 'RELIANCE', 'INFY', 'NIFTY50'

    Returns:
        dict with 'symbol', 'ltp', 'change', 'change_pct', 'timestamp'
    """
    if not _YF_AVAILABLE:
        return _stub_ltp(symbol)

    try:
        ticker = yf.Ticker(_nse_ticker(symbol))
        info = ticker.fast_info

        ltp = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", 0.0)
        prev_close = getattr(info, "previous_close", None) or getattr(info, "regularMarketPrice", ltp)
        if ltp is None or prev_close is None:
             return _stub_ltp(symbol)
        change = float(ltp) - float(prev_close)
        change_pct = (change / float(prev_close) * 100) if prev_close else 0.0

        return {
            "symbol": symbol.upper(),
            "ltp": round(float(ltp), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("get_ltp failed for %s: %s", symbol, exc)
        return _stub_ltp(symbol)


def get_ohlc(symbol: str, timeframe: str = "1d", lookback_days: int = 60) -> dict:
    """
    Fetch OHLC bars for a symbol.

    Args:
        symbol: NSE ticker, e.g. 'RELIANCE'
        timeframe: yfinance interval — '1m','5m','15m','1h','1d'
        lookback_days: Number of calendar days to fetch

    Returns:
        dict with 'symbol', 'timeframe', 'bars' (list of OHLCV dicts)
    """
    if not _YF_AVAILABLE:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "bars": [],
            "error": "yfinance not installed",
        }

    try:
        kwargs = {"interval": timeframe}
        if timeframe in ["1m", "2m", "5m", "15m"]:
            kwargs["period"] = "5d"
        elif timeframe in ["30m", "60m", "90m", "1h"]:
            kwargs["period"] = "1mo"
        else:
            kwargs["start"] = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        ticker = yf.Ticker(_nse_ticker(symbol))
        df = ticker.history(**kwargs)

        if df.empty:
            return {"symbol": symbol, "timeframe": timeframe, "bars": []}

        bars = [
            {
                "timestamp": idx.isoformat(),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ]
        return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": bars}

    except Exception as exc:
        logger.error("get_ohlc failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "timeframe": timeframe, "bars": [], "error": str(exc)}


def get_quote(symbol: str) -> dict:
    """
    Get a richer market quote with bid/ask/52w high-low.

    Args:
        symbol: NSE ticker

    Returns:
        dict with extended quote fields
    """
    if not _YF_AVAILABLE:
        return _stub_quote(symbol)

    try:
        ticker = yf.Ticker(_nse_ticker(symbol))
        info = ticker.info
        fast = ticker.fast_info

        return {
            "symbol": symbol.upper(),
            "company_name": info.get("longName", symbol),
            "ltp": round(float(fast.last_price or 0), 2),
            "open": round(float(fast.open or 0), 2),
            "prev_close": round(float(fast.previous_close or 0), 2),
            "day_high": round(float(fast.day_high or 0), 2),
            "day_low": round(float(fast.day_low or 0), 2),
            "week_52_high": round(float(info.get("fiftyTwoWeekHigh", 0)), 2),
            "week_52_low": round(float(info.get("fiftyTwoWeekLow", 0)), 2),
            "market_cap_cr": round(float(info.get("marketCap", 0)) / 1e7, 2),
            "volume": int(fast.three_month_average_volume or 0),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("get_quote failed for %s: %s", symbol, exc)
        return _stub_quote(symbol)


# ── Stubs for offline / testing ────────────────────────────────────────────────
def _stub_ltp(symbol: str) -> dict:
    price = round(random.uniform(500, 5000), 2)
    return {
        "symbol": symbol.upper(),
        "ltp": price,
        "change": round(random.uniform(-50, 50), 2),
        "change_pct": round(random.uniform(-2, 2), 2),
        "timestamp": datetime.now().isoformat(),
        "_stub": True,
    }


def _stub_quote(symbol: str) -> dict:
    stub = _stub_ltp(symbol)
    stub.update(
        {
            "company_name": f"{symbol.upper()} Ltd.",
            "open": stub["ltp"] - 10,
            "prev_close": stub["ltp"] - stub["change"],
            "day_high": stub["ltp"] + 20,
            "day_low": stub["ltp"] - 20,
            "week_52_high": stub["ltp"] + 200,
            "week_52_low": stub["ltp"] - 200,
            "market_cap_cr": 0,
            "volume": 0,
        }
    )
    return stub
