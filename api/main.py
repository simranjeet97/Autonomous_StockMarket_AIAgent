"""
api/main.py
───────────
FastAPI proxy server bridging the ADK Python Agents and the HTML Dashboard.
This allows the frontend JS to trigger real Python execution.

Run with:
uvicorn api.main:app --reload --port 8000
"""

import logging
import uuid
import json
import re
from contextlib import asynccontextmanager
import asyncio
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
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
from agents.news_research_agents import (
    SectorNewsAgent,
    GeopoliticalNewsAgent,
    NationalNewsAgent,
    WorldNewsAgent,
)

from core.database import AsyncSessionLocal, init_db
from core.models import AuditLog, SentimentAnalysis, TradeLog
from skills.market_data.tools import get_ltp, get_ohlc, get_quote
from skills.news.tools import _google_rss_search
from skills.technical_analysis.tools import calc_bollinger, calc_macd, calc_rsi

# Load env vars
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB
    await init_db()
    yield


app = FastAPI(title="StockMarket ADK Trading API", lifespan=lifespan)

# Enable CORS for the local dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/css", StaticFiles(directory="dashboard/css"), name="css")
app.mount("/js", StaticFiles(directory="dashboard/js"), name="js")


@app.get("/")
async def serve_root():
    return FileResponse("dashboard/index.html")


@app.get("/index.html")
async def serve_index():
    return FileResponse("dashboard/index.html")


@app.get("/news_research.html")
async def serve_news_research():
    return FileResponse("dashboard/news_research.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ── API Models ──────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    prompt: str = "Scan the market and find me trades"
    symbol: str | None = None


class SymbolRequest(BaseModel):
    symbol: str


class ExecuteRequest(BaseModel):
    symbol: str
    order_type: str
    price: float


# ── News Research Endpoints ──────────────────────────────────────────────────

@app.post("/api/news_research/sector")
async def run_sector_research() -> dict[str, Any]:
    logger.info("Executing SectorNewsAgent research...")
    try:
        response, state = await run_agent_and_get_state(
            agent=SectorNewsAgent,
            prompt="Perform deep sector research for the Indian stock market.",
            session_id=f"sector_research_{uuid.uuid4().hex[:8]}",
        )
        return {"status": "success", "agent": "SectorNewsAgent", "research": response}
    except Exception as e:
        logger.error("Error in SectorNewsAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/news_research/geopolitical")
async def run_geopolitical_research() -> dict[str, Any]:
    logger.info("Executing GeopoliticalNewsAgent research...")
    try:
        response, state = await run_agent_and_get_state(
            agent=GeopoliticalNewsAgent,
            prompt="Analyze global geopolitical events impacting India.",
            session_id=f"geo_research_{uuid.uuid4().hex[:8]}",
        )
        return {"status": "success", "agent": "GeopoliticalNewsAgent", "research": response}
    except Exception as e:
        logger.error("Error in GeopoliticalNewsAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/news_research/national")
async def run_national_research() -> dict[str, Any]:
    logger.info("Executing NationalNewsAgent research...")
    try:
        response, state = await run_agent_and_get_state(
            agent=NationalNewsAgent,
            prompt="Analyze Indian national and policy news.",
            session_id=f"national_research_{uuid.uuid4().hex[:8]}",
        )
        return {"status": "success", "agent": "NationalNewsAgent", "research": response}
    except Exception as e:
        logger.error("Error in NationalNewsAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/news_research/world")
async def run_world_research() -> dict[str, Any]:
    logger.info("Executing WorldNewsAgent research...")
    try:
        response, state = await run_agent_and_get_state(
            agent=WorldNewsAgent,
            prompt="Research world financial news and global trends.",
            session_id=f"world_research_{uuid.uuid4().hex[:8]}",
        )
        return {"status": "success", "agent": "WorldNewsAgent", "research": response}
    except Exception as e:
        logger.error("Error in WorldNewsAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Existing API Endpoints ──────────────────────────────────────────────────

@app.get("/api/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok", "message": "ADK Python API is running"}


@app.get("/api/history/{symbol}")
async def fetch_history(symbol: str) -> dict[str, Any]:
    try:
        return get_ohlc(symbol)
    except Exception as e:
        logger.error("Error fetching historical data: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news")
async def fetch_news() -> dict[str, Any]:
    try:
        return _google_rss_search("Indian stock market NSE", 7)
    except Exception as e:
        logger.error("Error fetching news: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quote/{symbol}")
async def fetch_quote(symbol: str) -> dict[str, Any]:
    try:
        quote = get_quote(symbol)
        ltp = get_ltp(symbol)
        return {"symbol": symbol, "ltp": ltp, "quote": quote}
    except Exception as e:
        logger.error("Error fetching quote: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/ws/market")
async def websocket_market_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_symbol = "RELIANCE"
    logger.info("WebSocket connection established. Default symbol: %s", current_symbol)
    try:
        while True:
            # Check for incoming messages to change symbol (non-blocking)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                if isinstance(data, dict) and "symbol" in data:
                    current_symbol = str(data["symbol"]).upper()
                    logger.info("WebSocket symbol changed to: %s", current_symbol)
            except asyncio.TimeoutError:
                # No incoming message, proceed to send data
                pass
            
            # Fetch LTP and send
            tb_data = get_ltp(current_symbol)
            await websocket.send_json(tb_data)
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error("WebSocket error: %s", e)


session_service = InMemorySessionService()


def extract_json(text: str) -> Optional[dict]:
    """Robustly extract JSON block from LLM response text."""
    try:
        # Try finding JSON within code blocks first
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # Fallback: Find anything that looks like a JSON object
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, Exception):
        pass
    return None


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
    async for event in runner.run_async(
        user_id="api_user", session_id=session_id, new_message=msg, state_delta=state_delta
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    final_text += p.text

    session = await session_service.get_session(
        app_name="StockMarket_ADK", user_id="api_user", session_id=session_id
    )
    if not session:
        return final_text, {}
    return final_text, session.state


@app.post("/api/scan/sentiment")
async def run_sentiment_scan() -> dict[str, Any]:
    try:
        response, state = await run_agent_and_get_state(
            agent=SentimentAgent,
            prompt="Analyze current market sentiment and build a 5-stock watchlist.",
            session_id=f"sentiment_scan_{uuid.uuid4().hex[:8]}",
        )
        sentiment_data = state.get("sentiment_analysis")
        
        # Refinement: Manually extract if output_key failed or was missing
        if not sentiment_data or isinstance(sentiment_data, str):
            sentiment_data = extract_json(response)
            
        if not sentiment_data:
            sentiment_data = {
                "market_sentiment": "NEUTRAL",
                "sentiment_score": 50,
                "macro_bias": "neutral",
                "watchlist": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"],
                "themes": ["System fallback used (parsing failed)"],
            }
        
        # Ensure themes key is present (normalise key_themes)
        if "themes" not in sentiment_data and "key_themes" in sentiment_data:
            sentiment_data["themes"] = sentiment_data["key_themes"]
        elif "themes" not in sentiment_data:
            sentiment_data["themes"] = []
            
        if "watchlist" not in sentiment_data:
            sentiment_data["watchlist"] = ["RELIANCE", "TCS", "INFY"]

        async with AsyncSessionLocal() as session:
            archive = SentimentAnalysis(
                market_sentiment=sentiment_data["market_sentiment"],
                sentiment_score=sentiment_data["sentiment_score"],
                macro_bias=sentiment_data["macro_bias"],
                watchlist=sentiment_data["watchlist"],
                themes=sentiment_data.get("themes", []),
            )
            session.add(archive)
            await session.commit()

        return {"status": "success", "message": response, "sentiment": sentiment_data}
    except Exception as e:
        logger.error("Error in SentimentAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/analyze")
async def run_technical_scan(req: SymbolRequest) -> dict[str, Any]:
    try:
        response, state = await run_agent_and_get_state(
            agent=analyst_agent, prompt=f"Analyze {req.symbol}", session_id=f"analyst_{req.symbol}"
        )
        signal_data = state.get("current_signal")
        
        # Refinement: Manually extract if output_key failed or was missing
        if not signal_data or isinstance(signal_data, str):
            signal_data = extract_json(response)
            
        if not signal_data:
            signal_data = {"symbol": req.symbol, "recommendation": "HOLD", "confidence": "0/6 indicators (fallback)"}

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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/risk")
async def run_risk_check(req: SymbolRequest) -> dict[str, Any]:
    try:
        state_delta = {"current_signal": {"symbol": req.symbol, "recommendation": "BUY"}}
        response, state = await run_agent_and_get_state(
            agent=risk_agent,
            prompt="Validate the proposed trade signal in session state.",
            session_id=f"risk_{req.symbol}",
            state_delta=state_delta,
        )
        approved = state.get("risk_approved", False)
        rule_checks = state.get("risk_details", [])

        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                agent_name="RiskAgent",
                action=f"Risk check for {req.symbol}",
                details={"approved": approved, "rule_checks": rule_checks},
            )
            session.add(audit)
            await session.commit()

        return {"status": "success", "approved": approved, "rule_checks": rule_checks}
    except Exception as e:
        logger.error("Error in RiskAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan/execute")
async def run_execution(req: ExecuteRequest) -> dict[str, Any]:
    try:
        state_delta = {
            "risk_approved": True,
            "current_signal": {"symbol": req.symbol, "recommendation": req.order_type, "price": req.price},
        }
        prompt = f"Executing {req.order_type} for {req.symbol} at {req.price}."
        response, state = await run_agent_and_get_state(
            agent=execution_agent,
            prompt=prompt,
            session_id=f"exec_{req.symbol}",
            state_delta=state_delta,
        )
        return {"status": "success", "message": response}
    except Exception as e:
        logger.error("Error in ExecutionAgent: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trade_logs")
async def get_trade_logs() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TradeLog).order_by(TradeLog.timestamp.desc()))
        logs = result.scalars().all()
        return {"status": "success", "logs": [
            {"symbol": l.symbol, "quantity": l.quantity, "price": l.price, "order_type": l.order_type, "timestamp": l.timestamp.isoformat()}
            for l in logs
        ]}


@app.get("/api/audit_logs")
async def get_audit_logs() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(50))
        logs = result.scalars().all()
        return {"status": "success", "logs": [{"agent_name": l.agent_name, "action": l.action, "timestamp": l.timestamp.isoformat()} for l in logs]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
