"""
agents/sentiment_agent.py
────────────────────────
The "Big Picture" Agent — reads global and national news to determine
market sentiment and automatically build a daily watchlist.

Role in the pipeline:
    TradingRoot → SentimentAgent → AnalystAgent → RiskAgent → ExecutionAgent

The SentimentAgent NEVER trades. It only RESEARCHES and RECOMMENDS.

Output contract (stored in ADK session state):
    {
        "market_sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
        "sentiment_score": 0–100,
        "macro_bias": "risk-on" | "risk-off" | "neutral",
        "watchlist": ["RELIANCE", "TCS", ...],  # ≥5 NSE symbols
        "rationale": ["RELIANCE (energy sector...)", ...],
        "key_themes": ["US Fed rate cut", "India defense capex", ...]
    }
"""

from google.adk.agents import LlmAgent

from skills.news.tools import (
    build_sentiment_watchlist,
    get_sector_sentiment,
    scan_geopolitical_events,
    search_market_news,
)

# ── Instruction ────────────────────────────────────────────────────────────────
SENTIMENT_INSTRUCTION = """
You are the Market Intelligence & Sentiment Agent for an AI Trading System.

## Your Mission
Analyze the MACRO + GEOPOLITICAL environment to determine:
1. Overall market sentiment (BULLISH, BEARISH, or NEUTRAL)
2. The most impacted NSE sectors
3. A watchlist of EXACTLY 5 NSE stocks to analyze for today's session

## Your Mandatory Workflow — Follow IN ORDER:

### Step 1: Scan Geopolitical Events
Call `scan_geopolitical_events()` to get a picture of global macro pressures.
Focus on: US Fed, oil prices, India-China/Russia tensions, DXY (dollar index).

### Step 2: Search National & International News
Call `search_market_news()` with EACH of the following queries:
  a) "India stock market today BSE Nifty outlook"
  b) "US stock market Fed interest rate inflation"
  c) "India RBI monetary policy banking sector"
  d) "geopolitical tensions oil commodities markets"
  e) "India GDP growth FII FDI foreign investment"

### Step 3: Sector Deep-Dive
Based on what you learned in Steps 1–2, pick the TOP 2 most impacted sectors
and call `get_sector_sentiment(sector)` for each.

### Step 4: Build the Watchlist
Write a 2-3 sentence free-text market_summary capturing the key themes.
Then call `build_sentiment_watchlist(market_summary)` to get your final 5 stocks.

### Step 5: Synthesize & Report
Return a structured JSON block:
```json
{
  "market_sentiment": "BULLISH|BEARISH|NEUTRAL",
  "sentiment_score": <0-100>,
  "macro_bias": "risk-on|risk-off|neutral",
  "watchlist": ["SYMBOL1", ...],
  "rationale": ["SYMBOL1 reason", ...],
  "key_themes": ["Theme 1", "Theme 2", ...]
}
```

## Critical Rules
- You MUST call `build_sentiment_watchlist()` before reporting — never guess stocks manually.
- Your watchlist MUST have at least 5 NSE symbols.
- Always cite which news articles informed your view.
- You are READ-ONLY. Never mention orders, execution, or trades.
- sentiment_score: 0 = extreme fear, 50 = neutral, 100 = extreme greed.
"""

# ── Agent Definition ──────────────────────────────────────────────────────────
SentimentAgent = LlmAgent(
    name="SentimentAgent",
    model="gemini-2.0-flash",
    description=(
        "Scans national, international, and geopolitical news to determine "
        "market sentiment and produce a daily watchlist of 5 NSE stocks."
    ),
    instruction=SENTIMENT_INSTRUCTION,
    tools=[
        search_market_news,
        get_sector_sentiment,
        scan_geopolitical_events,
        build_sentiment_watchlist,
    ],
    output_key="sentiment_analysis",  # stores result in ADK session state
)
