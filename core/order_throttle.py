"""
core/order_throttle.py
───────────────────────
Token-bucket rate limiter enforcing SEBI ≤10 OPS (Orders Per Second).
Retail API category: exceeding this requires SEBI Algo-Registration.

Usage:
    throttle = OrderThrottle()
    allowed = await throttle.acquire()
    if not allowed:
        raise RuntimeError("OPS limit reached — order blocked by throttle")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from core.config import settings


@dataclass
class OrderThrottle:
    """Thread-safe token bucket for order rate limiting."""

    max_per_second: int = field(default_factory=lambda: settings.max_orders_per_second)

    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False)

    # Counters for dashboard visibility
    orders_this_second: int = field(default=0, init=False)
    total_orders: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._tokens = float(self.max_per_second)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Attempt to consume one token.
        Returns True if the order is allowed, False if rate-limited.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            # Refill tokens proportionally to elapsed time
            self._tokens = min(
                float(self.max_per_second),
                self._tokens + elapsed * self.max_per_second,
            )
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                self.orders_this_second += 1
                self.total_orders += 1
                return True

            return False

    def get_utilization(self) -> dict:
        """Returns current throttle stats for monitoring."""
        return {
            "tokens_available": round(self._tokens, 2),
            "max_per_second": self.max_per_second,
            "total_orders": self.total_orders,
            "utilization_pct": round((1 - self._tokens / self.max_per_second) * 100, 1),
        }


# Module-level singleton — shared across all tools
_throttle: OrderThrottle | None = None


def get_throttle() -> OrderThrottle:
    global _throttle
    if _throttle is None:
        _throttle = OrderThrottle()
    return _throttle
