"""
core/session_manager.py
────────────────────────
Helpers for reading & writing ADK session state (trade context, signals,
approvals). The state dict is passed by the ADK runtime into every tool
and agent. This module provides type-safe getters / setters.
"""

from __future__ import annotations

from typing import Any

# ── State Keys ────────────────────────────────────────────────────────────────
KEY_ACTIVE_SYMBOL = "active_symbol"
KEY_SIGNAL = "current_signal"
KEY_RISK_APPROVED = "risk_approved"
KEY_DAILY_PNL = "daily_pnl_inr"
KEY_OPEN_POSITIONS = "open_positions"
KEY_TRADE_LOG = "trade_log"


def get_state(tool_context: Any, key: str, default: Any = None) -> Any:
    """Read a value from ADK tool context state."""
    return tool_context.state.get(key, default)


def set_state(tool_context: Any, key: str, value: Any) -> None:
    """Write a value into ADK tool context state."""
    tool_context.state[key] = value


def get_daily_pnl(tool_context: Any) -> float:
    return float(get_state(tool_context, KEY_DAILY_PNL, 0.0))


def update_daily_pnl(tool_context: Any, delta: float) -> float:
    """Add delta to daily P&L and return the new total."""
    current = get_daily_pnl(tool_context)
    new_pnl = current + delta
    set_state(tool_context, KEY_DAILY_PNL, new_pnl)
    return new_pnl


def append_trade_log(tool_context: Any, entry: dict) -> None:
    log: list = get_state(tool_context, KEY_TRADE_LOG, [])
    log.append(entry)
    set_state(tool_context, KEY_TRADE_LOG, log)


def reset_session(tool_context: Any) -> None:
    """Clear trading state at start of new market session."""
    set_state(tool_context, KEY_DAILY_PNL, 0.0)
    set_state(tool_context, KEY_RISK_APPROVED, False)
    set_state(tool_context, KEY_OPEN_POSITIONS, [])
    set_state(tool_context, KEY_TRADE_LOG, [])
