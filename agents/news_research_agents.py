"""
agents/news_research_agents.py
──────────────────────────────
Specialized research agents for parallel news analysis and stock impact finding.
All agents are built using Google ADK and use the tools in news_tools.py.
"""

from google.adk.agents import LlmAgent
from skills.news.tools import (
    search_market_news,
    search_yahoo_finance_news,
    get_sector_sentiment,
    analyze_news_impact,
)

# ── Sector News Agent ──────────────────────────────────────────────────────────
SectorNewsAgent = LlmAgent(
    name="SectorNewsAgent",
    model="gemini-3-flash-preview",
    description="Researches deep into specific NSE sectors to find impactful news and stocks.",
    instruction="""
    You are the Sector Research Specialist.
    Your goal is to identify which specific sectors (IT, Banking, Energy, etc.) are currently 
    experiencing the most volatility or opportunity based on news.
    
    Workflow:
    1. Search for 'Indian stock market sector outlook' using search_market_news.
    2. Pick the top 3 most mentioned or relevant sectors.
    3. For each sector, call get_sector_sentiment(sector).
    4. For every significant news article found, call analyze_news_impact to get a list of stocks.
    5. Return a structured report. YOU MUST explicitly categorize the impacted stocks into two buckets based on your analysis:
       - 🟢 **Top Stocks to Invest (LONG)**: <Symbol> - <1-sentence reason>
       - 🔴 **Top Stocks to Short (SELL)**: <Symbol> - <1-sentence reason>
    """,
    tools=[search_market_news, get_sector_sentiment, analyze_news_impact],
)

# ── Geopolitical News Agent ────────────────────────────────────────────────────
GeopoliticalNewsAgent = LlmAgent(
    name="GeopoliticalNewsAgent",
    model="gemini-3-flash-preview",
    description="Analyzes global events and their macro impact on Indian markets.",
    instruction="""
    You are the Global Macro & Geopolitical Analyst.
    Your goal is to monitor international conflicts, trade wars, Fed decisions, and oil prices.
    
    Workflow:
    1. Search for 'global geopolitical news impact on markets' and 'US Fed interest rate news'.
    2. Identify key international events affecting India.
    3. Use analyze_news_impact for every event to see which Indian sectors or stocks are at risk or benefit.
    4. Return a structured report. YOU MUST explicitly categorize the impacted stocks into two buckets based on your analysis:
       - 🟢 **Top Stocks to Invest (LONG)**: <Symbol> - <1-sentence reason>
       - 🔴 **Top Stocks to Short (SELL)**: <Symbol> - <1-sentence reason>
    """,
    tools=[search_market_news, analyze_news_impact],
)

# ── National & Policy Agent ────────────────────────────────────────────────────
NationalNewsAgent = LlmAgent(
    name="NationalNewsAgent",
    model="gemini-3-flash-preview",
    description="Focuses on Indian national news, RBI policies, and government regulations.",
    instruction="""
    You are the National Policy & Economy Expert.
    Your focus is on India-specific news: RBI decisions, SEBI regulations, Budget updates, and National infrastructure.
    
    Workflow:
    1. Search for 'RBI monetary policy', 'India government policy news stock market', and 'BSE NSE regulation news'.
    2. Identify policy changes that hit specific industries (e.g., changes in taxes, subsidies).
    3. Use analyze_news_impact to list specific companies impacted by these national news items.
    4. Return a structured report. YOU MUST explicitly categorize the impacted stocks into two buckets based on your analysis:
       - 🟢 **Top Stocks to Invest (LONG)**: <Symbol> - <1-sentence reason>
       - 🔴 **Top Stocks to Short (SELL)**: <Symbol> - <1-sentence reason>
    """,
    tools=[search_market_news, analyze_news_impact],
)

# ── World News & Finance Agent ────────────────────────────────────────────────
WorldNewsAgent = LlmAgent(
    name="WorldNewsAgent",
    model="gemini-3-flash-preview",
    description="Researches world financial news and global market trends.",
    instruction="""
    You are the World Financial News Researcher.
    You look at global markets (Wall Street, European markets, Asian markets) and broad financial trends.
    
    Workflow:
    1. Use search_yahoo_finance_news for general global financial trends.
    2. Look for 'world economy growth' or 'global inflation' news.
    3. Determine the 'Macro Bias' (Risk-On or Risk-Off) based on global sentiment.
    4. Use analyze_news_impact to see which EXPORT-oriented Indian stocks (like IT/Pharma) are impacted.
    5. Return a structured report. YOU MUST explicitly categorize the impacted stocks into two buckets based on your analysis:
       - 🟢 **Top Stocks to Invest (LONG)**: <Symbol> - <1-sentence reason>
       - 🔴 **Top Stocks to Short (SELL)**: <Symbol> - <1-sentence reason>
    """,
    tools=[search_yahoo_finance_news, analyze_news_impact],
)
