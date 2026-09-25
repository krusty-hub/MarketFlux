"""
MarketFlux – Binance WebSocket Price Feed
Connects to Binance's real-time trade stream for live price data.
Maintains a singleton price manager that caches latest prices.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("marketflux.price_feed")


class PriceFeed:
    """
    Singleton price feed manager that connects to Binance WebSocket streams
    and maintains a cache of latest prices.
    """
    _instance: Optional[PriceFeed] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Price cache: { "BTCUSDT": 104250.50, "ETHUSDT": 3450.75 }
        self._prices: Dict[str, float] = {}
        self._last_update: Dict[str, float] = {}

        # WebSocket task reference
        self._ws_task: Optional[asyncio.Task] = None
        self._running = False

        # Subscribers for price updates (callbacks)
        self._subscribers: List[Callable] = []

        # Symbols to track
        self._symbols: Set[str] = {"btcusdt", "ethusdt", "bnbusdt", "solusdt"}

    @property
    def prices(self) -> Dict[str, float]:
        return dict(self._prices)

    def get_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol (case-insensitive)."""
        return self._prices.get(symbol.upper())

    def subscribe(self, callback: Callable):
        """Register a callback for price updates: callback(symbol, price)."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        """Remove a price update callback."""
        self._subscribers = [cb for cb in self._subscribers if cb != callback]

    async def start(self):
        """Start the WebSocket connection to Binance."""
        if self._running:
            log.info("Price feed already running")
            return

        self._running = True
        self._ws_task = asyncio.create_task(self._connect_loop())
        log.info("Price feed started")

    async def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        log.info("Price feed stopped")

    async def _connect_loop(self):
        """
        Main connection loop with automatic reconnection.
        Connects to Binance combined stream for multiple symbols.
        """
        import websockets

        # Build combined stream URL
        streams = "/".join(f"{s}@trade" for s in self._symbols)
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        while self._running:
            try:
                log.info(f"Connecting to Binance WebSocket: {len(self._symbols)} symbols")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    log.info("Binance WebSocket connected")
                    async for raw_msg in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw_msg)
                            data = msg.get("data", msg)
                            if data.get("e") == "trade":
                                symbol = data["s"]  # e.g. "BTCUSDT"
                                price = float(data["p"])
                                self._prices[symbol] = price
                                self._last_update[symbol] = time.time()

                                # Notify subscribers
                                for cb in self._subscribers:
                                    try:
                                        result = cb(symbol, price)
                                        if asyncio.iscoroutine(result):
                                            await result
                                    except Exception as e:
                                        log.warning(f"Subscriber callback error: {e}")
                        except (json.JSONDecodeError, KeyError) as e:
                            log.debug(f"Skipping malformed message: {e}")

            except asyncio.CancelledError:
                log.info("Price feed task cancelled")
                break
            except Exception as e:
                log.warning(f"Binance WebSocket disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    def get_status(self) -> Dict[str, Any]:
        """Return the current status of the price feed."""
        now = time.time()
        return {
            "running": self._running,
            "tracked_symbols": list(s.upper() for s in self._symbols),
            "cached_prices": {k: round(v, 2) for k, v in self._prices.items()},
            "last_update": {
                k: round(now - v, 1) for k, v in self._last_update.items()
            },
            "subscriber_count": len(self._subscribers),
        }


# Module-level singleton
price_feed = PriceFeed()
