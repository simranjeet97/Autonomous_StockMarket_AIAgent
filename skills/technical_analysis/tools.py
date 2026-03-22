"""
tools/technical_analysis_tools.py
───────────────────────────────────
Technical indicator tools used by the Analyst Agent.
Powered by pandas-ta for fast, vectorized computation.
Falls back to manual NumPy implementation if pandas-ta is unavailable.
"""

from __future__ import annotations

import logging

import numpy as np

from skills.market_data.tools import get_ohlc

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    import pandas_ta as ta  # type: ignore

    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False
    logger.warning("pandas-ta not installed — using simple numpy fallback")


def _fetch_close(symbol: str, period: int = 60) -> pd.Series:
    """Fetch closing prices as a pandas Series."""
    data = get_ohlc(symbol, timeframe="1d", lookback_days=max(period * 2, 120))
    bars = data.get("bars", [])
    if not bars:
        return None  # type: ignore

    closes = pd.Series(
        [b["close"] for b in bars],
        index=pd.to_datetime([b["timestamp"] for b in bars]),
        name="close",
    )
    return closes


def _fetch_df(symbol: str, period: int = 60) -> pd.DataFrame:
    """Fetch full OHLCV as a DataFrame."""
    data = get_ohlc(symbol, timeframe="1d", lookback_days=max(period * 2, 120))
    bars = data.get("bars", [])
    if not bars:
        return None  # type: ignore

    df = pd.DataFrame(bars)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    return df


def calc_rsi(symbol: str, period: int = 14) -> dict:
    """
    Calculate the Relative Strength Index (RSI) for a symbol.

    Args:
        symbol: NSE ticker (e.g., 'RELIANCE')
        period: RSI lookback period (default 14)

    Returns:
        dict with 'rsi', 'signal' (oversold/overbought/neutral), 'bars_used'
    """
    try:
        closes = _fetch_close(symbol, period)
        if closes is None or len(closes) < period + 1:
            return {
                "symbol": symbol,
                "rsi": None,
                "signal": "insufficient_data",
                "error": "Not enough bars",
            }

        if _TA_AVAILABLE:

            rsi_series = ta.rsi(closes, length=period)
            rsi_val = float(rsi_series.dropna().iloc[-1])
        else:
            # Simple NumPy RSI
            delta = np.diff(closes.values)
            gains = np.where(delta > 0, delta, 0)
            losses = np.where(delta < 0, -delta, 0)
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi_val = 100 - (100 / (1 + rs))

        rsi_val = round(rsi_val, 2)
        signal = "oversold" if rsi_val < 30 else ("overbought" if rsi_val > 70 else "neutral")

        return {
            "symbol": symbol.upper(),
            "indicator": "RSI",
            "period": period,
            "rsi": rsi_val,
            "signal": signal,
            "interpretation": f"RSI={rsi_val:.1f} → {signal.upper()}",
            "bars_used": len(closes),
        }
    except Exception as exc:
        logger.error("calc_rsi failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "rsi": None, "signal": "error", "error": str(exc)}


def calc_macd(
    symbol: str,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> dict:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        symbol: NSE ticker
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal_period: Signal line EMA period (default 9)

    Returns:
        dict with 'macd', 'signal_line', 'histogram', 'crossover_signal'
    """
    try:
        closes = _fetch_close(symbol, period=slow + signal_period + 10)
        if closes is None or len(closes) < slow + signal_period:
            return {"symbol": symbol, "macd": None, "signal": "insufficient_data"}

        if _TA_AVAILABLE:
            macd_df = ta.macd(closes, fast=fast, slow=slow, signal=signal_period)
            last_row = macd_df.dropna().iloc[-1]
            macd_val = round(float(last_row.iloc[0]), 4)
            hist_val = round(float(last_row.iloc[1]), 4)
            signal_val = round(float(last_row.iloc[2]), 4)
        else:
            # NumPy EMA MACD
            def ema(series, span):
                k = 2 / (span + 1)
                result = [series[0]]
                for v in series[1:]:
                    result.append(v * k + result[-1] * (1 - k))
                return np.array(result)

            v = closes.values.astype(float)
            fast_ema = ema(v, fast)
            slow_ema = ema(v, slow)
            macd_line = fast_ema - slow_ema
            signal_line = ema(macd_line[slow - 1 :], signal_period)
            hist = macd_line[slow + signal_period - 2 :] - signal_line

            macd_val = round(float(macd_line[-1]), 4)
            signal_val = round(float(signal_line[-1]), 4)
            hist_val = round(float(hist[-1]), 4)

        crossover = "bullish_crossover" if hist_val > 0 else "bearish_crossover"

        return {
            "symbol": symbol.upper(),
            "indicator": "MACD",
            "macd_line": macd_val,
            "signal_line": signal_val,
            "histogram": hist_val,
            "crossover_signal": crossover,
            "interpretation": (
                f"MACD={macd_val:.3f} Signal={signal_val:.3f} Hist={hist_val:.3f} → {crossover.upper()}"
            ),
        }
    except Exception as exc:
        logger.error("calc_macd failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "macd": None, "signal": "error", "error": str(exc)}


def calc_bollinger(symbol: str, period: int = 20, std_dev: float = 2.0) -> dict:
    """
    Calculate Bollinger Bands for a symbol.

    Args:
        symbol: NSE ticker
        period: Moving average window (default 20)
        std_dev: Number of standard deviations for bands (default 2.0)

    Returns:
        dict with 'upper_band', 'middle_band', 'lower_band', 'bandwidth', 'signal'
    """
    try:
        closes = _fetch_close(symbol, period=period + 20)
        if closes is None or len(closes) < period:
            return {"symbol": symbol, "upper_band": None, "signal": "insufficient_data"}

        if _TA_AVAILABLE:
            bb = ta.bbands(closes, length=period, std=std_dev)  # type: ignore[arg-type]
            last = bb.dropna().iloc[-1]
            upper = round(float(last.iloc[0]), 2)
            mid = round(float(last.iloc[1]), 2)
            lower = round(float(last.iloc[2]), 2)
        else:
            v = closes.values[-period:].astype(float)
            mid = np.mean(v)
            std = np.std(v)
            upper = mid + std_dev * std
            lower = mid - std_dev * std
            upper, mid, lower = round(upper, 2), round(mid, 2), round(lower, 2)

        current_price = float(closes.iloc[-1])
        bandwidth = round((upper - lower) / mid * 100, 2)

        if current_price >= upper:
            bb_signal = "overbought_squeeze"
        elif current_price <= lower:
            bb_signal = "oversold_bounce"
        else:
            bb_signal = "within_bands"

        return {
            "symbol": symbol.upper(),
            "indicator": "Bollinger Bands",
            "period": period,
            "upper_band": upper,
            "middle_band": mid,
            "lower_band": lower,
            "current_price": round(current_price, 2),
            "bandwidth_pct": bandwidth,
            "signal": bb_signal,
            "interpretation": (
                f"Price ₹{current_price:.0f} | Bands [{lower:.0f}–{upper:.0f}] → {bb_signal.upper()}"
            ),
        }
    except Exception as exc:
        logger.error("calc_bollinger failed for %s: %s", symbol, exc)
        return {"symbol": symbol, "upper_band": None, "signal": "error", "error": str(exc)}


def scan_signals(symbol: str) -> dict:
    """
    Run all three indicators and return a consolidated trade signal.

    Args:
        symbol: NSE ticker to scan

    Returns:
        dict with aggregated 'recommendation' (BUY/SELL/HOLD) and all indicator data
    """
    rsi = calc_rsi(symbol)
    macd = calc_macd(symbol)
    bb = calc_bollinger(symbol)

    buy_votes = 0
    sell_votes = 0

    if rsi.get("signal") == "oversold":
        buy_votes += 1
    elif rsi.get("signal") == "overbought":
        sell_votes += 1

    if macd.get("crossover_signal") == "bullish_crossover":
        buy_votes += 1
    elif macd.get("crossover_signal") == "bearish_crossover":
        sell_votes += 1

    if bb.get("signal") == "oversold_bounce":
        buy_votes += 1
    elif bb.get("signal") == "overbought_squeeze":
        sell_votes += 1

    if buy_votes >= 2:
        recommendation = "BUY"
        confidence = f"{buy_votes}/3 indicators bullish"
    elif sell_votes >= 2:
        recommendation = "SELL"
        confidence = f"{sell_votes}/3 indicators bearish"
    else:
        recommendation = "HOLD"
        confidence = "Mixed signals — no clear direction"

    return {
        "symbol": symbol.upper(),
        "recommendation": recommendation,
        "confidence": confidence,
        "buy_votes": buy_votes,
        "sell_votes": sell_votes,
        "rsi": rsi,
        "macd": macd,
        "bollinger": bb,
    }
