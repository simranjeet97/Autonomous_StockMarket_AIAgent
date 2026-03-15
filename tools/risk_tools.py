"""
tools/risk_tools.py
────────────────────
The "Hard Gate" Risk Tool.

The RiskAgent calls validate_risk() before ANY order is placed.
This is a DETERMINISTIC, white-box function — not an LLM judgment.
It returns False if any rule is violated, which physically blocks
the ExecutionAgent from calling place_nifty_order().
"""

from __future__ import annotations

import logging
from datetime import datetime
from datetime import time as dt_time

from core.config import settings

logger = logging.getLogger(__name__)

# ── Market Hours (NSE) ─────────────────────────────────────────────────────────
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)


def _is_market_open() -> bool:
    """Check if NSE market is currently open."""
    now = datetime.now().time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


def validate_risk(
    symbol: str,
    quantity: int,
    order_type: str,
    daily_pnl_inr: float = 0.0,
    current_positions: int = 0,
    estimated_order_value_inr: float = 0.0,
) -> dict:
    """
    Hard-gate risk validator for every trade signal.

    Enforces SEBI 2026 compliant rules and personal risk parameters.
    ExecutionAgent MUST NOT place an order if approved == False.

    Args:
        symbol: NSE stock ticker (e.g., 'RELIANCE', 'NIFTY50')
        quantity: Number of shares / lots
        order_type: 'BUY' or 'SELL'
        daily_pnl_inr: Cumulative P&L for today in INR (negative = loss)
        current_positions: Total number of currently open positions
        estimated_order_value_inr: Approximate order value for position check

    Returns:
        dict with 'approved' (bool), 'reason' (str), and 'checks' (list)
    """
    checks: list[dict] = []
    rejected_reasons: list[str] = []

    # ── Rule 1: Daily Loss Limit ──────────────────────────────────────────────
    max_loss = settings.max_daily_loss_inr
    if daily_pnl_inr <= -max_loss:
        reason = f"Daily loss limit breached: ₹{daily_pnl_inr:.0f} (max -₹{max_loss:.0f})"
        checks.append({"rule": "daily_loss_limit", "passed": False, "detail": reason})
        rejected_reasons.append(reason)
    else:
        checks.append(
            {
                "rule": "daily_loss_limit",
                "passed": True,
                "detail": f"P&L ₹{daily_pnl_inr:.0f} within limit",
            }
        )

    # ── Rule 2: Position Limit ────────────────────────────────────────────────
    max_pos = settings.max_position_lots
    if order_type == "BUY" and current_positions >= max_pos:
        reason = f"Max positions reached: {current_positions}/{max_pos}"
        checks.append({"rule": "position_limit", "passed": False, "detail": reason})
        rejected_reasons.append(reason)
    else:
        checks.append(
            {
                "rule": "position_limit",
                "passed": True,
                "detail": f"Positions {current_positions}/{max_pos}",
            }
        )

    # ── Rule 3: Market Hours ──────────────────────────────────────────────────
    if not _is_market_open():
        reason = "Market is currently closed (NSE: 09:15–15:30 IST)"
        checks.append({"rule": "market_hours", "passed": False, "detail": reason})
        rejected_reasons.append(reason)
    else:
        checks.append({"rule": "market_hours", "passed": True, "detail": "Market is open"})

    # ── Rule 4: Quantity Sanity Check ─────────────────────────────────────────
    if quantity <= 0:
        reason = f"Invalid quantity: {quantity}"
        checks.append({"rule": "quantity_check", "passed": False, "detail": reason})
        rejected_reasons.append(reason)
    else:
        checks.append(
            {"rule": "quantity_check", "passed": True, "detail": f"Quantity {quantity} is valid"}
        )

    # ── Rule 5: Order Type Validation ─────────────────────────────────────────
    if order_type not in ("BUY", "SELL"):
        reason = f"Invalid order_type: '{order_type}' — must be BUY or SELL"
        checks.append({"rule": "order_type", "passed": False, "detail": reason})
        rejected_reasons.append(reason)
    else:
        checks.append(
            {"rule": "order_type", "passed": True, "detail": f"Order type '{order_type}' is valid"}
        )

    approved = len(rejected_reasons) == 0
    summary = "All risk checks passed ✅" if approved else " | ".join(rejected_reasons)

    logger.info(
        "Risk validation for %s qty=%d %s | approved=%s | %s",
        symbol,
        quantity,
        order_type,
        approved,
        summary,
    )

    return {
        "approved": approved,
        "reason": summary,
        "checks": checks,
        "symbol": symbol,
        "quantity": quantity,
        "order_type": order_type,
    }


def get_risk_summary(daily_pnl_inr: float, current_positions: int) -> dict:
    """
    Returns a dashboard-friendly risk utilization snapshot.

    Args:
        daily_pnl_inr: Today's cumulative P&L in INR
        current_positions: Number of open positions

    Returns:
        dict with utilization percentages for the UI
    """
    max_loss = settings.max_daily_loss_inr
    max_pos = settings.max_position_lots

    loss_pct = min(100, abs(min(daily_pnl_inr, 0)) / max_loss * 100)
    pos_pct = min(100, current_positions / max_pos * 100)

    return {
        "daily_pnl_inr": daily_pnl_inr,
        "loss_utilization_pct": round(loss_pct, 1),
        "position_utilization_pct": round(pos_pct, 1),
        "max_daily_loss_inr": max_loss,
        "max_positions": max_pos,
        "market_open": _is_market_open(),
    }
