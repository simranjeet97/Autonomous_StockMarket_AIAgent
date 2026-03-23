import os
from google.adk.agents import LlmAgent

SCREENER_QUERY_SYSTEM = """
You are an expert at Screener.in query syntax.
Convert user's natural language stock question into a valid Screener.in screen query.

Screener query rules:
- Fields: Market Cap, P/E, ROE, ROCE, Sales growth, Profit growth, Debt to equity, Current ratio
- Operators: >, <, =, AND, OR
- Example: "Market Cap > 500 AND ROE > 15 AND P/E < 20 AND Sales growth > 10"

Return ONLY the raw query string, nothing else.
"""

screener_query_agent = LlmAgent(
    name="ScreenerQueryAgent",
    model="gemini-2.0-flash",
    instruction=SCREENER_QUERY_SYSTEM,
)
