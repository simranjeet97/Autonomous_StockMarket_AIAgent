import json
import yfinance as yf
from google.adk.agents import LlmAgent
import google.generativeai as genai
from tools.screener_scraper import run_screener_query

RANKING_SYSTEM = """
You are a senior equity analyst for Indian stock markets.
Given a list of stocks with their financial data, rank them from most to least attractive for investment.

For each stock output:
- rank (1 = best)
- ticker
- investment_score (0-100)
- allocation_pct (suggested portfolio %, all must sum to 100)
- rationale (2 sentences max)

Return ONLY valid JSON array. No markdown.
"""

def enrich_stock(stock: dict) -> dict:
    """Add live metrics from yfinance for NSE stocks"""
    name = stock.get("Name", "")
    try:
        # yfinance uses .NS suffix for NSE
        ticker_raw = stock.get("url", "").split("/company/")[-1].split("/")[0]
        if ticker_raw:
            yf_ticker = yf.Ticker(f"{ticker_raw}.NS")
            info = yf_ticker.info
            stock["market_cap_cr"] = round(info.get("marketCap", 0) / 1e7, 1)
            stock["52w_high"] = info.get("fiftyTwoWeekHigh")
            stock["52w_low"] = info.get("fiftyTwoWeekLow")
            stock["analyst_rating"] = info.get("recommendationKey", "n/a")
    except Exception as e:
        print(f"Error enriching {name}: {e}")
        pass
    return stock


def screener_full_pipeline(user_query: str, screener_query: str) -> list:
    """Full pipeline: scrape → enrich → rank"""
    # 1. Scrape Screener.in
    try:
        stocks = run_screener_query(screener_query)
    except Exception as e:
        print(f"Scraping error: {e}")
        return [{"rank": 1, "ticker": "ERROR", "investment_score": 0, "allocation_pct": 0, "rationale": f"Scraping failed: {str(e)}"}]
        
    if not stocks:
        return []

    # 2. Enrich with yfinance data
    stocks = [enrich_stock(s) for s in stocks[:20]]  # cap at 20

    # 3. Pass to LLM ranker
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        f"{RANKING_SYSTEM}\\n\\nUser intent: {user_query}\\n\\nStocks:\\n{json.dumps(stocks, indent=2)}"
    )
    
    # Strip markdown block if present
    text_response = response.text.strip()
    if text_response.startswith("```json"):
        text_response = text_response.replace("```json", "", 1)
    if text_response.endswith("```"):
        text_response = text_response[::-1].replace("```", "", 1)[::-1]
        
    try:
        ranked = json.loads(text_response.strip())
        return sorted(ranked, key=lambda x: x.get("rank", 999))
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Response: {text_response}")
        return []
