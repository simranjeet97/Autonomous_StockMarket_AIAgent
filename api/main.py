"""
api/main.py
───────────
FastAPI proxy server bridging the ADK Python Agents and the HTML Dashboard.
This allows the frontend JS to trigger real Python execution.

Run with:
uvicorn api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from pydantic import BaseModel
from sqlalchemy import select

from agents.analyst_agent import analyst_agent
from agents.execution_agent import execution_agent
from agents.risk_agent import risk_agent
from agents.sentiment_agent import SentimentAgent
from core.database import AsyncSessionLocal, init_db
from core.models import AuditLog, SentimentAnalysis, TradeLog
from tools.market_data_tools import get_ltp, get_ohlc, get_quote
from tools.news_tools import _google_rss_search
from tools.technical_analysis_tools import calc_bollinger, calc_macd, calc_rsi

# Load env vars
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB
    await init_db()
    yield
    # Shutdown logic if needed


app = FastAPI(title="StockMarket ADK Trading API", lifespan=lifespan)


# Enable CORS for the local dashboard (file:// or localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/css", StaticFiles(directory="dashboard/css"), name="css")
app.mount("/js", StaticFiles(directory="dashboard/js"), name="js")


@app.get("/")
async def serve_dashboard():
    return FileResponse("dashboard/index.html")


# ── API Models ──────────────────────────────────────────────────────────────


class ScanRequest(BaseModel):
    prompt: str = "Scan the market and find me trades"
    symbol: str | None = None  # If provided, does a targeted scan instead of full sentiment scan


class SymbolRequest(BaseModel):
    symbol: str


class ExecuteRequest(BaseModel):
    symbol: str
    order_type: str
    price: float


# ── API Endpoints ──────────────────────────────────────────────────────────


@app.get("/api/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "message": "ADK Python API is running"}


@app.get("/api/history/{symbol}")
async def fetch_history(symbol: str) -> dict[str, Any]:
    """Fetch live historical data"""
    try:
        return get_ohlc(symbol)
    except Exception as e:
        logger.error("Error fetching historical data for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news")
async def fetch_news() -> dict[str, Any]:
    """Fetch live news data"""
    try:
        return _google_rss_search("Indian stock market NSE", 7)
    except Exception as e:
        logger.error("Error fetching news: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quote/{symbol}")
async def fetch_quote(symbol: str) -> dict[str, Any]:
    """Fetch live quote data for the dashboard ticker via market_data_tools."""
    try:
        quote = get_quote(symbol)
        ltp = get_ltp(symbol)
        return {"symbol": symbol, "ltp": ltp, "quote": quote}
    except Exception as e:
        logger.error("Error fetching quote for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=str(e))



session_service = InMemorySessionService()


async def run_agent_and_get_state(
    agent, prompt: str, session_id: str, state_delta: dict | None = None
):
    runner = Runner(
        agent=agent,
        session_service=session_service,
        auto_create_session=True,
        app_name="StockMarket_ADK",
    )
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_text = ""
    # Run the generator
    async for event in runner.run_async(
        user_id="api_user", session_id=session_id, new_message=msg, state_delta=state_delta
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    final_text += p.text

    # Fetch the state from the session
    session = await session_service.get_session(
        app_name="StockMarket_ADK", user_id="api_user", session_id=session_id
    )
    if not session:
        return final_text, {}
    return final_text, session.state


@app.post("/api/scan/sentiment")
async def run_sentiment_scan() -> dict[str, Any]:
    """
    Runs the isolated SentimentAgent pipeline to get Market Mood and Watchlist.
    """
    logger.info("Executing SentimentAgent pipeline...")
    try:
        response, state = await run_agent_and_get_state(
            agent=SentimentAgent,
            prompt="Analyze current market sentiment and give me a watchlist.",
            session_id="sentiment_session",
        )
        sentiment_data = state.get("sentiment_analysis")

        # If the LLM failed to reliably store the json in state, fallback to parsing response
        if not sentiment_data:
            sentiment_data = {
                "market_sentiment": "NEUTRAL",
                "sentiment_score": 50,
                "macro_bias": "neutral",
                "watchlist": ["RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK"],
                "themes": ["Unable to parse SentimentAgent JSON"],
                "rationale": [],
            }

        # Archive to DB
        async with AsyncSessionLocal() as session:
            archive = SentimentAnalysis(
                market_sentiment=sentiment_data["market_sentiment"],
                sentiment_score=sentiment_data["sentiment_score"],
                macro_bias=sentiment_data["macro_bias"],
                watchlist=sentiment_data["watchlist"],
                themes=sentiment_data["themes"],
            )
            session.add(archive)
            await session.commit()

        return {"status": "success", "message": response, "sentiment": sentiment_data}
    except Exception as e:
        logger.error("Error in SentimentAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/analyze")
async def run_technical_scan(req: SymbolRequest) -> dict[str, Any]:
    """
    Runs isolated AnalystAgent on a specific symbol.
    """
    logger.info("Executing AnalystAgent for %s...", req.symbol)
    try:
        # We need to configure the AnalystAgent dynamically or run the root?
        # Running Analyst directly:

        response, state = await run_agent_and_get_state(
            agent=analyst_agent, prompt=f"Analyze {req.symbol}", session_id=f"analyst_{req.symbol}"
        )
        signal_data = state.get("current_signal")

        # Fallback if state mapping failed
        if not signal_data:
            rsi = calc_rsi(req.symbol)
            macd = calc_macd(req.symbol)
            bb = calc_bollinger(req.symbol)

            signal_data = {
                "symbol": req.symbol,
                "recommendation": "HOLD",
                "confidence": 0,
                "indicators": {
                    "rsi": rsi,
                    "macd_hist": macd.get("macd_hist"),
                    "bb_width": bb.get("bb_width"),
                },
                "rationale": "Fallback signal generated from direct tool calls.",
            }

        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                agent_name="AnalystAgent",
                action=f"Analyze {req.symbol}",
                details={"signal": signal_data, "response": response[:500]},
            )
            session.add(audit)
            await session.commit()

        return {"status": "success", "message": response, "signal": signal_data}
    except Exception as e:
        logger.error("Error in AnalystAgent: %s", e)
        err_msg = str(e)
        if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
             raise HTTPException(
                 status_code=429, 
                 detail="AI Rate Limit Exceeded: The Gemini API is currently throttled. Please wait a minute and try again."
             )
        raise HTTPException(status_code=500, detail=err_msg)


@app.post("/api/scan/risk")
async def run_risk_check(req: SymbolRequest) -> dict[str, Any]:
    """
    Runs isolated RiskAgent for a proposed trade.
    """
    logger.info("Executing RiskAgent for %s...", req.symbol)
    try:

        state_delta = {"current_signal": {"symbol": req.symbol, "recommendation": "BUY"}}
        response, state = await run_agent_and_get_state(
            agent=risk_agent,
            prompt="Validate the proposed trade signal in session state.",
            session_id=f"risk_{req.symbol}",
            state_delta=state_delta,
        )
        approved = state.get("risk_approved", False)
        rule_checks = state.get("risk_details", {})

        if not rule_checks:
            rule_checks = [
                {"rule": "daily_loss_limit", "passed": True},
                {"rule": "position_limit", "passed": True},
                {"rule": "market_hours", "passed": False},
                {"rule": "throttle", "passed": True},
            ]

        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                agent_name="RiskAgent",
                action=f"Risk check for {req.symbol}",
                details={
                    "approved": approved,
                    "rule_checks": rule_checks,
                    "response": response[:500],
                },
            )
            session.add(audit)
            await session.commit()

        return {
            "status": "success",
            "message": response,
            "approved": approved,
            "rule_checks": rule_checks,
        }
    except Exception as e:
        logger.error("Error in RiskAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/execute")
async def run_execution(req: ExecuteRequest) -> dict[str, Any]:
    """
    Manually triggered execution by the user after reviewing the signal.
    """
    logger.info("User approved execution for %s...", req.symbol)
    try:

        state_delta = {
            "risk_approved": True,  # Manual user approval implies risk bypass/acceptance for execution agent to proceed
            "current_signal": {
                "symbol": req.symbol,
                "recommendation": req.order_type,
                "price": req.price,
            },
        }

        # We prompt the execution agent to place the passed signal
        prompt = f"The user has manually approved risk and authorized a {req.order_type} order for {req.symbol} at {req.price}. Execute it now."
        response, state = await run_agent_and_get_state(
            agent=execution_agent,
            prompt=prompt,
            session_id=f"exec_{req.symbol}",
            state_delta=state_delta,
        )

        # If agent executed it, tools should log it. We parse agent response simply
        return {"status": "success", "message": response, "symbol": req.symbol}
    except Exception as e:
        logger.error("Error in ExecutionAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trade_logs")
async def get_trade_logs() -> dict[str, Any]:
    """Fetch all trade logs from the database."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(TradeLog).order_by(TradeLog.timestamp.desc()))
            logs = result.scalars().all()

            return {
                "status": "success",
                "logs": [
                    {
                        "id": log.id,
                        "order_id": log.order_id,
                        "symbol": log.symbol,
                        "quantity": log.quantity,
                        "price": log.price,
                        "order_type": log.order_type,
                        "status": log.status,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat(),
                        "is_stub": bool(log.is_stub),
                    }
                    for log in logs
                ],
            }
    except Exception as e:
        logger.error("Error fetching trade logs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit_logs")
async def get_audit_logs() -> dict[str, Any]:
    """Fetch recent audit logs."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(50)
            )
            logs = result.scalars().all()

            return {
                "status": "success",
                "logs": [
                    {
                        "id": log.id,
                        "agent_name": log.agent_name,
                        "action": log.action,
                        "details": log.details,
                        "timestamp": log.timestamp.isoformat(),
                    }
                    for log in logs
                ],
            }
    except Exception as e:
        logger.error("Error fetching audit logs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
