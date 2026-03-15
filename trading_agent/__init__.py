"""
trading_agent/__init__.py
──────────────────────────
ADK package init — exports `root_agent` for `adk web .` discovery.
"""

from trading_agent.agent import root_agent

__all__ = ["root_agent"]
