from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.screener_query_agent import screener_query_agent
from agents.screener_analyst_agent import screener_full_pipeline

router = APIRouter(prefix="/screener")

class AnalyzePayload(BaseModel):
    query: str

@router.post("/analyze")
async def analyze_stocks(payload: AnalyzePayload):
    user_query = payload.query

    try:
        # Step 1: Translate to Screener syntax
        response = await screener_query_agent.run(user_query)
        screener_query = response.text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query generation failed: {e}")

    try:
        # Step 2: Run full pipeline
        ranked_stocks = screener_full_pipeline(user_query, screener_query)
        return {
            "screener_query": screener_query,
            "results": ranked_stocks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {e}")
