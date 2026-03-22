"""
tools/news_tools.py
───────────────────
News & Sentiment Intelligence tools for the Trading Agent.

These are read-only observer tools — they NEVER place orders.
They feed the SentimentAgent which decides the stock watchlist.

Sources (in priority order):
1. GNews API  (free tier: 100 req/day — set GNEWS_API_KEY in .env)
2. Google RSS  (no key needed — limited to ~20 headlines)
3. GDELT Project (no key — geopolitical event database)

All functions return clean dicts with a "_source" field so the
agent can cite where the news came from.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

# ── NSE Sector → Representative Stocks Mapping ──────────────────────────────
# Used by the Sentiment Agent to translate news themes → tradeable symbols.
SECTOR_TO_STOCKS: dict[str, list[str]] = {
    "it": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"],
    "energy": ["RELIANCE", "ONGC", "IOC", "BPCL", "POWERGRID"],
    "defense": ["HAL", "BEL", "BHEL", "COCHINSHIP", "GRSE"],
    "pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA"],
    "auto": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT"],
    "fmcg": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
    "metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "SAILSTEEL", "COALINDIA"],
    "realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE"],
    "telecom": ["BHARTIARTL", "IDEA", "TATACOMM"],
    "infra": ["ADANIPORTS", "L&T", "IRCON", "KEC", "ABB"],
    "consumption": ["TITAN", "DMART", "ABFRL", "TRENT", "NYKAA"],
}

# Geopolitical keyword → sector affected (NSE-specific heuristics)
GEOPOLITICAL_IMPACT: dict[str, list[str]] = {
    "war": ["defense", "energy", "metal"],
    "sanctions": ["energy", "it", "banking"],
    "fed rate": ["banking", "it", "realty"],
    "rbi": ["banking", "fmcg", "realty"],
    "oil": ["energy", "auto", "fmcg"],
    "dollar": ["it", "pharma", "metal"],
    "china": ["metal", "auto", "defense"],
    "russia": ["defense", "energy", "metal"],
    "ukraine": ["defense", "energy"],
    "usd": ["it", "pharma"],
    "inflation": ["fmcg", "banking", "auto"],
    "recession": ["it", "fmcg", "pharma"],
    "ai": ["it", "telecom"],
    "semiconductor": ["it", "defense"],
    "budget": ["banking", "infra", "defense"],
    "election": ["infra", "banking", "consumption"],
    "monsoon": ["fmcg", "auto", "consumption"],
}


# ── Tool 1: Search Market News ────────────────────────────────────────────────
def search_market_news(query: str, max_articles: int = 10) -> dict[str, Any]:
    """
    Search for the latest financial news headlines matching a query.

    Uses GNews API if GNEWS_API_KEY is set, else falls back to Google RSS.

    Args:
        query: Search term, e.g. 'India stock market', 'US Fed rate decision',
               'geopolitical tensions oil price', 'RBI monetary policy'
        max_articles: Maximum number of articles to return (default 10)

    Returns:
        dict with:
          - query (str): The search query used
          - articles (list): Each article has title, source, published_at, url, summary
          - total (int): Number of articles returned
          - _source (str): Which data source was used
    """
    try:
        return _gnews_search(query, max_articles)
    except Exception as e:
        logger.warning("GNews failed (%s), falling back to Google RSS", e)
        try:
            return _google_rss_search(query, max_articles)
        except Exception as e2:
            logger.error("Google RSS also failed: %s", e2)
            return _stub_news(query)


def _gnews_search(query: str, max_articles: int) -> dict[str, Any]:
    """Fetches news via GNews API (requires GNEWS_API_KEY)."""
    api_key = getattr(settings, "gnews_api_key", None)
    if not api_key:
        raise ValueError("GNEWS_API_KEY not configured")

    encoded = urllib.parse.quote(query)
    url = (
        f"https://gnews.io/api/v4/search"
        f"?q={encoded}&lang=en&country=in&max={max_articles}"
        f"&token={api_key}"
    )
    with urllib.request.urlopen(url, timeout=8) as resp:
        data = json.loads(resp.read())

    articles = [
        {
            "title": a.get("title", ""),
            "source": a.get("source", {}).get("name", "Unknown"),
            "published_at": a.get("publishedAt", ""),
            "url": a.get("url", ""),
            "summary": a.get("description", "")[:300],
        }
        for a in data.get("articles", [])[:max_articles]
    ]
    return {"query": query, "articles": articles, "total": len(articles), "_source": "gnews"}


def _google_rss_search(query: str, max_articles: int) -> dict[str, Any]:
    """Fetches news via Google News RSS (no API key needed)."""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    items = root.findall(".//item")[:max_articles]
    articles = []
    for item in items:
        title = item.findtext("title", "")
        source = item.findtext("source", "")
        pub_date = item.findtext("pubDate", "")
        link = item.findtext("link", "")
        desc = item.findtext("description", "")
        # Strip HTML tags from description
        clean_desc = re.sub(r"<[^>]+>", "", desc)[:300]
        articles.append(
            {
                "title": title,
                "source": source,
                "published_at": pub_date,
                "url": link,
                "summary": clean_desc.strip(),
            }
        )

    return {"query": query, "articles": articles, "total": len(articles), "_source": "google_rss"}


# ── Tool 2: Get Sector Sentiment ──────────────────────────────────────────────
def get_sector_sentiment(sector: str) -> dict[str, Any]:
    """
    Get latest news and sentiment for a specific market sector.

    Searches for news about the given sector and returns both the headlines
    AND a list of representative NSE stocks to watch.

    Args:
        sector: One of: 'it', 'banking', 'energy', 'defense', 'pharma',
                'auto', 'fmcg', 'metal', 'realty', 'telecom', 'infra', 'consumption'

    Returns:
        dict with:
          - sector (str)
          - stocks (list[str]): Representative NSE symbols for this sector
          - articles (list): Latest news headlines
          - sentiment_hint (str): 'positive' | 'negative' | 'neutral'
          - _source (str)
    """
    sector = sector.lower().strip()
    stocks = SECTOR_TO_STOCKS.get(sector, [])

    # Build a query tailored to the sector
    query_map = {
        "it": "India IT sector outlook TCS Infosys earnings",
        "banking": "RBI interest rate India banking sector NPA",
        "energy": "crude oil price ONGC Reliance India energy",
        "defense": "India defense sector HAL budget orders",
        "pharma": "India pharma FDA approval drug exports",
        "auto": "India auto sales EV market Maruti Tata",
        "fmcg": "India FMCG rural demand Hindustan Unilever ITC",
        "metal": "steel iron ore prices Tata Steel JSW",
        "realty": "India real estate housing DLF Godrej",
        "telecom": "India telecom Jio Airtel 5G spectrum",
        "infra": "India infrastructure capex L&T NHAI",
        "consumption": "India urban consumption retail growth",
    }
    query = query_map.get(sector, f"India {sector} sector stocks news")
    news_data = search_market_news(query, max_articles=5)

    # Naïve sentiment scoring on titles
    positive_words = {
        "surge",
        "rally",
        "gain",
        "profit",
        "record",
        "growth",
        "beat",
        "upgrade",
        "buy",
        "strong",
        "boost",
    }
    negative_words = {
        "fall",
        "drop",
        "loss",
        "slump",
        "cut",
        "downgrade",
        "sell",
        "weak",
        "crash",
        "decline",
        "risk",
    }

    score = 0
    for a in news_data.get("articles", []):
        words = a["title"].lower().split()
        score += sum(1 for w in words if w in positive_words)
        score -= sum(1 for w in words if w in negative_words)

    sentiment_hint = "positive" if score > 0 else "negative" if score < 0 else "neutral"

    return {
        "sector": sector,
        "stocks": stocks,
        "articles": news_data.get("articles", []),
        "sentiment_hint": sentiment_hint,
        "score": score,
        "_source": news_data.get("_source", "unknown"),
    }


# ── Tool 3: Geopolitical Event Scan ──────────────────────────────────────────
def scan_geopolitical_events() -> dict[str, Any]:
    """
    Scan for major geopolitical and macroeconomic events that affect
    Indian markets (currency, trade, commodity prices).

    Searches for: US Fed decisions, India-China relations,
    Middle East oil tensions, Russia-Ukraine, dollar index, RBI decisions.

    Returns:
        dict with:
          - events (list): Key global events
          - affected_sectors (list[str]): Sectors likely to be impacted
          - watchlist (list[str]): Recommended NSE stocks to watch
          - macro_bias (str): 'risk-on' | 'risk-off' | 'neutral'
          - _source (str)
    """
    geo_queries = [
        "US Federal Reserve interest rate decision 2024",
        "India geopolitical tensions defense",
        "crude oil OPEC price war conflict",
        "US dollar index DXY impact emerging markets",
        "India China trade relations",
    ]

    all_articles: list[dict] = []
    affected_sector_set: set[str] = set()

    for q in geo_queries:
        try:
            res = search_market_news(q, max_articles=3)
            all_articles.extend(res.get("articles", []))
            # Keyword match to identify affected sectors
            for a in res.get("articles", []):
                combined = (a["title"] + " " + a.get("summary", "")).lower()
                for keyword, sectors in GEOPOLITICAL_IMPACT.items():
                    if keyword in combined:
                        affected_sector_set.update(sectors)
        except Exception as e:
            logger.warning("Geo query failed for '%s': %s", q, e)

    # Build consolidated watchlist from affected sectors
    watchlist: list[str] = []
    for sector in list(affected_sector_set)[:4]:
        stocks = SECTOR_TO_STOCKS.get(sector, [])
        for s in stocks[:2]:
            if s not in watchlist:
                watchlist.append(s)

    # Determine macro bias
    risk_off_sectors = {"defense", "energy", "metal"}
    risk_on_sectors = {"it", "consumption", "realty"}
    risk_off_count = len(affected_sector_set & risk_off_sectors)
    risk_on_count = len(affected_sector_set & risk_on_sectors)
    macro_bias = (
        "risk-off"
        if risk_off_count > risk_on_count
        else ("risk-on" if risk_on_count > risk_off_count else "neutral")
    )

    return {
        "events": all_articles[:6],
        "affected_sectors": list(affected_sector_set),
        "watchlist": watchlist[:10],
        "macro_bias": macro_bias,
        "timestamp": datetime.now(UTC).isoformat(),
        "_source": "multi_query_synthesis",
    }


# ── Tool 4: Build Dynamic Watchlist ──────────────────────────────────────────
def build_sentiment_watchlist(market_summary: str) -> dict[str, Any]:
    """
    Given a market summary string (from the SentimentAgent's analysis),
    extract the top 5 NSE stocks to focus on for today's session.

    This is the FINAL step the SentimentAgent calls before handing off
    to the AnalystAgent.

    Args:
        market_summary: A free-text description of the current market environment,
                        e.g. "IT sector is bullish due to strong US earnings.
                              Defense is in focus due to border tensions.
                              Oil is high, so energy stocks are a watch."

    Returns:
        dict with:
          - watchlist (list[str]): Top 5 NSE symbols selected
          - sectors_identified (list[str]): Sectors detected in the summary
          - rationale (str): One-liner reason for each stock
          - count (int)
    """
    summary_lower = market_summary.lower()
    scored_sectors: dict[str, int] = {}

    for keyword, sectors in GEOPOLITICAL_IMPACT.items():
        if keyword in summary_lower:
            for s in sectors:
                scored_sectors[s] = scored_sectors.get(s, 0) + 1

    # Also check direct sector name mentions
    for sector in SECTOR_TO_STOCKS:
        if sector in summary_lower:
            scored_sectors[sector] = scored_sectors.get(sector, 0) + 2

    # Sort sectors by mention frequency
    ranked_sectors = sorted(scored_sectors, key=lambda s: scored_sectors[s], reverse=True)

    watchlist: list[str] = []
    rationales: list[str] = []
    for sector in ranked_sectors:
        stocks = SECTOR_TO_STOCKS.get(sector, [])
        for stock in stocks[:2]:
            if stock not in watchlist:
                watchlist.append(stock)
                rationales.append(f"{stock} ({sector.upper()} sector impacted)")
            if len(watchlist) >= 5:
                break
        if len(watchlist) >= 5:
            break

    # Fallback: if no matches, use Nifty top-5 by liquidity
    if not watchlist:
        watchlist = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY"]
        rationales = [
            "RELIANCE (high liquidity fallback)",
            "TCS (high liquidity fallback)",
            "HDFCBANK (high liquidity fallback)",
            "ICICIBANK (high liquidity fallback)",
            "INFY (high liquidity fallback)",
        ]

    return {
        "watchlist": watchlist[:5],
        "rationale": rationales[:5],
        "sectors_identified": ranked_sectors[:5],
        "count": min(5, len(watchlist)),
    }


# ── Tool 4: Yahoo Finance News Search ──────────────────────────────────────────
def search_yahoo_finance_news(query: str, max_articles: int = 5) -> dict[str, Any]:
    """
    Search for news headlines specifically from Yahoo Finance via RSS.
    """
    try:
        encoded = urllib.parse.quote(query)
        # Yahoo Finance doesn't have a direct search RSS like Google, 
        # but we can use their top stories or general finance news
        url = f"https://finance.yahoo.com/rss/topstories"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=settings.news_timeout_sec) as resp:
            xml_bytes = resp.read()

        root = ET.fromstring(xml_bytes)
        items = root.findall(".//item")[:max_articles]
        articles = []
        for item in items:
            title = item.findtext("title", "")
            # Only include if query matches title (basic filtering since it's top stories)
            if query.lower() in title.lower() or not query:
                articles.append({
                    "title": title,
                    "source": "Yahoo Finance",
                    "published_at": item.findtext("pubDate", ""),
                    "url": item.findtext("link", ""),
                    "summary": re.sub(r"<[^>]+>", "", item.findtext("description", ""))[:300].strip(),
                })
        
        return {"query": query, "articles": articles, "total": len(articles), "_source": "yahoo_finance"}
    except Exception as e:
        logger.error("Yahoo Finance RSS failed: %s", e)
        return {"query": query, "articles": [], "total": 0, "_source": "yahoo_finance_failed"}


# ── Tool 5: Analyze News Impact ──────────────────────────────────────────────
def analyze_news_impact(headline: str, summary: str) -> list[str]:
    """
    Analyze a news headline/summary to identify specific NSE stocks potentially impacted.
    
    This is intended to be called by an LLM agent as a tool.
    It returns a list of potential NSE symbols.
    NOTE FOR LLM: You MUST analyze the news yourself to determine if the impact on these stocks is BULLISH (Long) or BEARISH (Short).
    """
    impacted_stocks = []
    combined = (headline + " " + summary).lower()
    
    # 1. Check sectoral mapping
    for sector, stocks in SECTOR_TO_STOCKS.items():
        if sector in combined:
            impacted_stocks.extend(stocks[:2])
            
    # 2. Check keyword mapping
    for keyword, sectors in GEOPOLITICAL_IMPACT.items():
        if keyword in combined:
            for s in sectors:
                impacted_stocks.extend(SECTOR_TO_STOCKS.get(s, [])[:1])

    # 3. Direct symbol mentions (basic heuristic)
    # Most NSE symbols are uppercase and 3-10 chars
    potential_symbols = re.findall(r"\b[A-Z]{3,10}\b", headline + " " + summary)
    for sym in potential_symbols:
        # Check if it's in our known list or looks like a typical NSE symbol
        if sym not in impacted_stocks and len(impacted_stocks) < 10:
            impacted_stocks.append(sym)

    return list(set(impacted_stocks))[:10]


# ── Tool 6: Parallel News Research (Synthesizer) ──────────────────────────────
def synthesize_research(sector_news: list, geo_news: list, national_news: list, world_news: list) -> dict[str, Any]:
    """
    Synthesizes results from multiple research agents into a cohesive report.
    """
    all_articles = sector_news + geo_news + national_news + world_news
    
    # Identify unique stocks across all news
    all_stocks = []
    for art in all_articles:
        impacts = analyze_news_impact(art.get("title", ""), art.get("summary", ""))
        art["impacted_stocks"] = impacts
        all_stocks.extend(impacts)
        
    return {
        "summary": f"Analyzed {len(all_articles)} news items across 4 categories.",
        "top_impacted_stocks": list(set(all_stocks))[:15],
        "detailed_news": all_articles,
        "timestamp": datetime.now(UTC).isoformat()
    }


# ── Stub fallback ──────────────────────────────────────────────────────────────
def _stub_news(query: str) -> dict[str, Any]:
    """Returns placeholder news when all sources are unavailable."""
    return {
        "query": query,
        "articles": [
            {
                "title": "Markets await RBI policy decision amid global uncertainty",
                "source": "STUB_DATA",
                "published_at": datetime.now(UTC).isoformat(),
                "url": "",
                "summary": "Simulated headline — configure GNEWS_API_KEY for live news.",
            }
        ],
        "total": 1,
        "_source": "stub",
    }
