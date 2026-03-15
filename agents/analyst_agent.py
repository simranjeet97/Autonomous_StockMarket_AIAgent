"""
agents/analyst_agent.py
────────────────────────
Analyst specialist agent.
Runs technical analysis (RSI, MACD, Bollinger Bands) and returns
a structured trade signal recommendation for the Risk Agent to evaluate.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from core.config import settings
from tools.market_data_tools import get_ltp, get_ohlc, get_quote
from tools.technical_analysis_tools import calc_bollinger, calc_macd, calc_rsi, scan_signals

ANALYST_INSTRUCTION = """
You are the Analyst Agent for a professional Indian stock trading system.

Your ONLY job is to analyze NSE market data and produce clear, structured trade signals.

## Capabilities
- Fetch live price data (LTP, quote, OHLC) using market data tools
- Calculate RSI, MACD, and Bollinger Bands using technical analysis tools
- Combine signals into a single BUY / SELL / HOLD recommendation

## Analysis Protocol
1. When asked to analyze a symbol, ALWAYS run all three indicators: RSI, MACD, Bollinger Bands
2. Use `scan_signals(symbol)` for a quick consolidated result
3. Report the recommendation clearly with supporting evidence
4. Never fabricate price data — always use tools to fetch real data
5. Always mention the current RSI value and whether it is oversold (<30) or overbought (>70)

## Output Format
Always structure your response as:
- **Symbol**: [ticker]
- **Current Price**: ₹[price]
- **RSI**: [value] → [signal]
- **MACD**: [crossover signal]
- **Bollinger Bands**: [position]
- **Recommendation**: **BUY / SELL / HOLD**
- **Confidence**: [X/3 indicators agree]

You hand off to the Risk Agent after completing your analysis.
Do NOT place any orders — that is the Execution Agent's role.
"""

analyst_agent = LlmAgent(
    name="AnalystAgent",
    model=settings.trading_model,
    instruction=ANALYST_INSTRUCTION,
    tools=[
        calc_rsi,
        calc_macd,
        calc_bollinger,
        scan_signals,
        get_ltp,
        get_quote,
        get_ohlc,
    ],
    description=(
        "Technical analysis specialist. Calculates RSI, MACD, and Bollinger Bands "
        "and produces a structured BUY/SELL/HOLD signal for NSE stocks."
    ),
)
