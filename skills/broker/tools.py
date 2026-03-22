"""
tools/broker_tools.py
──────────────────────
ADK tools for order management via Indian broker APIs.
Default target: Dhan (dhanhq SDK).

SECURITY: All credentials are loaded from environment — never hard-coded.
SAFETY:   Every order call first acquires a throttle token (≤10 OPS).
          Orders placed here have already passed validate_risk().
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Literal

from core.config import settings
from core.database import AsyncSessionLocal
from core.models import TradeLog
from core.order_throttle import get_throttle

try:
    from kiteconnect import KiteConnect
    _KITE_AVAILABLE = True
except ImportError:
    _KITE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Broker SDK initialisation (lazy) ──────────────────────────────────────────
_broker_client = None
_broker_type = None  # "KITE" | "STUB"


def _get_broker():
    """Lazy-init the broker client (Kite) so import works without credentials."""
    global _broker_client, _broker_type
    if _broker_client is not None:
        return _broker_client, _broker_type

    # Try Kite (Zerodha) if API Key and Access Token are provided
    if settings.kite_api_key and settings.kite_access_token and _KITE_AVAILABLE:
        try:
            _broker_client = KiteConnect(api_key=settings.kite_api_key)
            _broker_client.set_access_token(settings.kite_access_token)
            _broker_type = "KITE"
            logger.info("Zerodha (Kite) client initialised.")
            return _broker_client, _broker_type
        except Exception as exc:
            logger.warning("Kite init failed (%s) — falling back to stub", exc)

    # Stub mode fallback
    logger.warning("No Kite credentials found or SDK missing — running in stub mode")
    _broker_client = "STUB"
    _broker_type = "STUB"
    return _broker_client, _broker_type


# ── Helper ─────────────────────────────────────────────────────────────────────
def _check_throttle() -> bool:
    """Synchronous throttle check (tools run in sync context)."""
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(get_throttle().acquire())
    except RuntimeError:
        # No running event loop — run in new loop
        return asyncio.run(get_throttle().acquire())


# ── Tool: place_nifty_order ────────────────────────────────────────────────────
def place_nifty_order(
    symbol: str,
    quantity: int,
    order_type: Literal["BUY", "SELL"],
    product: str = "INTRADAY",
    price: float = 0.0,
    trigger_price: float = 0.0,
) -> dict:
    """
    Place a limit/market order on NSE via Dhan broker API.

    ONLY call this after validate_risk() has returned approved=True.

    Args:
        symbol: NSE ticker (e.g., 'RELIANCE', 'NIFTY50')
        quantity: Number of shares or lots
        order_type: 'BUY' or 'SELL'
        product: 'INTRADAY' (default) or 'DELIVERY'
        price: Limit price in INR (0 = market order)
        trigger_price: SL trigger price (0 = no stop-loss trigger)

    Returns:
        dict with 'order_id', 'status', 'message', and order details
    """
    # ── Throttle gate ─────────────────────────────────────────────
    if not _check_throttle():
        return {
            "status": "REJECTED",
            "message": "Order rejected: OPS rate limit exceeded (>10/sec)",
            "symbol": symbol,
            "quantity": quantity,
            "order_type": order_type,
        }

    client, b_type = _get_broker()

    if b_type == "STUB":
        return _stub_order(symbol, quantity, order_type, product)

    try:
        if b_type == "KITE":

            transaction = (
                client.TRANSACTION_TYPE_BUY if order_type == "BUY" else client.TRANSACTION_TYPE_SELL
            )
            order_mode = client.ORDER_TYPE_MARKET if price == 0.0 else client.ORDER_TYPE_LIMIT
            prod = client.PRODUCT_MIS if product == "INTRADAY" else client.PRODUCT_CNC

            # Zerodha format: NSE:RELIANCE
            trade_symbol = symbol.replace(".NS", "")

            order_id = client.place_order(
                tradingsymbol=trade_symbol,
                exchange=client.EXCHANGE_NSE,
                transaction_type=transaction,
                quantity=quantity,
                order_type=order_mode,
                product=prod,
                price=price,
                trigger_price=trigger_price,
                variety=client.VARIETY_REGULAR,
            )

            logger.info(
                "Zerodha Order placed: %s %d %s @ ₹%.2f", order_type, quantity, symbol, price
            )

            res = {
                "order_id": order_id,
                "status": "OPEN",
                "message": "Order submitted to Zerodha (Kite)",
                "symbol": symbol,
                "quantity": quantity,
                "order_type": order_type,
                "price": price,
                "timestamp": datetime.now().isoformat(),
            }
            _save_trade_to_db(res, is_stub=False)
            return res

        return {
            "status": "ERROR",
            "message": f"Unsupported broker type: {b_type}",
            "symbol": symbol,
            "order_type": order_type,
        }

    except Exception as exc:
        logger.error("place_nifty_order failed: %s", exc)
        return {
            "status": "ERROR",
            "message": str(exc),
            "symbol": symbol,
            "order_type": order_type,
        }


def cancel_order(order_id: str) -> dict:
    """
    Cancel an open order by its ID.

    Args:
        order_id: The broker-assigned order ID to cancel

    Returns:
        dict with 'status' and 'message'
    """
    client, b_type = _get_broker()

    if b_type == "STUB":
        return {"order_id": order_id, "status": "CANCELLED", "message": "Stub: order cancelled"}

    try:
        if b_type == "KITE":
            client.cancel_order(variety=client.VARIETY_REGULAR, order_id=order_id)
            return {
                "order_id": order_id,
                "status": "CANCELLED",
                "message": "Cancel request submitted to Kite",
            }
        return {"order_id": order_id, "status": "ERROR", "message": f"Unsupported broker: {b_type}"}
    except Exception as exc:
        return {"order_id": order_id, "status": "ERROR", "message": str(exc)}


def get_positions() -> dict:
    """
    Fetch all open positions from the broker.

    Returns:
        dict with 'positions' list and 'total_count'
    """
    client, b_type = _get_broker()

    if b_type == "STUB":
        return {"positions": [], "total_count": 0, "_stub": True}

    try:
        if b_type == "KITE":
            positions = client.positions().get("net", [])
            return {"positions": positions, "total_count": len(positions)}
        return {"positions": [], "total_count": 0, "error": f"Unsupported broker: {b_type}"}
    except Exception as exc:
        return {"positions": [], "total_count": 0, "error": str(exc)}


def get_order_book() -> dict:
    """
    Retrieve today's order book.

    Returns:
        dict with 'orders' list
    """
    client, b_type = _get_broker()

    if b_type == "STUB":
        return {"orders": [], "_stub": True}

    try:
        if b_type == "KITE":
            orders = client.orders()
            return {"orders": orders}
        return {"orders": [], "error": f"Unsupported broker: {b_type}"}
    except Exception as exc:
        return {"orders": [], "error": str(exc)}


# ── Stub helper ────────────────────────────────────────────────────────────────
def _stub_order(symbol: str, quantity: int, order_type: str, product: str) -> dict:
    """Return a simulated order response when broker credentials are absent."""
    fake_id = f"STUB-{uuid.uuid4().hex[:8].upper()}"
    logger.info("STUB order: %s %d %s [%s]", order_type, quantity, symbol, fake_id)
    res = {
        "order_id": fake_id,
        "status": "PENDING",
        "message": f"Stub order — Dhan not configured. Would {order_type} {quantity} {symbol} ({product})",
        "symbol": symbol,
        "quantity": quantity,
        "order_type": order_type,
        "timestamp": datetime.now().isoformat(),
        "_stub": True,
    }
    _save_trade_to_db(res, is_stub=True)
    return res


def _save_trade_to_db(order_data: dict, is_stub: bool = False):
    """Helper to persist trade to SQLite from sync context."""

    async def _async_save():
        async with AsyncSessionLocal() as session:
            trade = TradeLog(
                order_id=order_data["order_id"],
                symbol=order_data["symbol"],
                quantity=order_data["quantity"],
                price=order_data.get("price", 0.0),
                order_type=order_data["order_type"],
                status=order_data["status"],
                message=order_data["message"],
                is_stub=1 if is_stub else 0,
            )
            session.add(trade)
            await session.commit()

    try:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.ensure_future(_async_save())
            else:
                loop.run_until_complete(_async_save())
        except RuntimeError:
            # No running loop in this thread, try to get from any thread or start one
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(_async_save())
            except Exception:
                # Fallback: create a new loop for this task
                asyncio.run(_async_save())
    except Exception as e:
        logger.error("Failed to save trade to DB: %s", e)
