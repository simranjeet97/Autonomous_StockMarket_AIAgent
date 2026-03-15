"""
core/models.py
──────────────
Database models for Trade logs, Sentiment analysis, and Audit logs.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class TradeLog(Base):
    """Permanent record of all trade executions."""

    __tablename__ = "trade_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(10))  # BUY / SELL
    status: Mapped[str] = mapped_column(String(20))  # OPEN / COMPLETED / ERROR
    message: Mapped[str] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_stub: Mapped[bool] = mapped_column(Integer, default=0)  # 1 for stub, 0 for real


class SentimentAnalysis(Base):
    """Archived market sentiment scans."""

    __tablename__ = "sentiment_archives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_sentiment: Mapped[str] = mapped_column(String(20))  # BULLISH / BEARISH / NEUTRAL
    sentiment_score: Mapped[float] = mapped_column(Float)
    macro_bias: Mapped[str] = mapped_column(String(20))
    watchlist: Mapped[list[str]] = mapped_column(JSON)
    themes: Mapped[list[str]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Trace of critical agent decisions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
