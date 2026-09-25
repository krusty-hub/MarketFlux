"""
MarketFlux – Risk Management Background Worker
Continuously monitors open positions against risk rules (SL, TP, drawdown).
Auto-closes positions when stop-loss or take-profit is hit.
Auto-halts the bot when daily loss or max drawdown is breached.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from . import portfolio_service as portfolio
from . import position_service as positions
from . import activity_log_service as activity
from .price_feed import price_feed

log = logging.getLogger("marketflux.risk_worker")

# Interval between risk checks (seconds)
RISK_CHECK_INTERVAL = 5


class RiskWorker:
    """
    Background asyncio task that periodically:
    1. Updates all position prices from the live feed
    2. Checks SL/TP triggers and auto-closes positions
    3. Checks daily loss cap & max drawdown limits
    """
    _instance: Optional[RiskWorker] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._monitored_users: set = set()

    def register_user(self, user_id: str):
        """Register a user for risk monitoring."""
        self._monitored_users.add(user_id)

    def unregister_user(self, user_id: str):
        """Unregister a user from risk monitoring."""
        self._monitored_users.discard(user_id)

    async def start(self):
        """Start the background risk monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        log.info("Risk worker started")

    async def stop(self):
        """Stop the background risk monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Risk worker stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                for user_id in list(self._monitored_users):
                    await self._check_user_positions(user_id)
                    await self._check_portfolio_limits(user_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Risk worker error: {e}")

            await asyncio.sleep(RISK_CHECK_INTERVAL)

    async def _check_user_positions(self, user_id: str):
        """
        Update prices and check SL/TP for all open positions.
        """
        open_pos = positions.get_open_positions(user_id)
        if not open_pos:
            return

        for pos in open_pos:
            symbol = pos["symbol"]
            symbol_key = symbol.replace("/", "")
            current_price = price_feed.get_price(symbol_key)

            if current_price is None:
                continue

            # Update position with live price
            positions.update_position_price(pos["id"], current_price)

            entry_price = float(pos["entry_price"])
            direction = pos["direction"]
            stop_loss = pos.get("stop_loss")
            take_profit = pos.get("take_profit")
            size = float(pos["size"])

            # Calculate unrealized P&L
            if direction == "LONG":
                unrealized_pnl = (current_price - entry_price) * size
            else:
                unrealized_pnl = (entry_price - current_price) * size

            # ── Check Stop Loss ──
            if stop_loss is not None:
                stop_loss = float(stop_loss)
                sl_hit = (
                    (direction == "LONG" and current_price <= stop_loss) or
                    (direction == "SHORT" and current_price >= stop_loss)
                )
                if sl_hit:
                    log.info(f"STOP LOSS hit for {pos['id']}: {symbol} @ ${current_price:,.2f}")
                    await self._auto_close(user_id, pos["id"], current_price, "STOP_LOSS")
                    continue

            # ── Check Take Profit ──
            if take_profit is not None:
                take_profit = float(take_profit)
                tp_hit = (
                    (direction == "LONG" and current_price >= take_profit) or
                    (direction == "SHORT" and current_price <= take_profit)
                )
                if tp_hit:
                    log.info(f"TAKE PROFIT hit for {pos['id']}: {symbol} @ ${current_price:,.2f}")
                    await self._auto_close(user_id, pos["id"], current_price, "TAKE_PROFIT")
                    continue

        # Update portfolio equity after all positions are updated
        port = portfolio.get_or_create_portfolio(user_id)
        unrealized = positions.calculate_total_unrealized_pnl(user_id)
        paper_balance = float(port.get("paper_balance", 10000.0))
        portfolio.update_equity(user_id, paper_balance, unrealized)

    async def _check_portfolio_limits(self, user_id: str):
        """
        Check if daily loss or max drawdown limits have been breached.
        If so, auto-halt all positions.
        """
        port = portfolio.get_or_create_portfolio(user_id)
        risk = portfolio.get_risk_settings(user_id)

        equity = float(port.get("equity", 10000.0))
        peak_equity = float(port.get("peak_equity", 10000.0))
        today_pnl = float(port.get("today_pnl", 0.0))

        # Daily loss check
        max_daily_loss_pct = float(risk.get("max_daily_loss_pct", 4.0))
        if peak_equity > 0 and today_pnl < 0:
            daily_loss_pct = (abs(today_pnl) / peak_equity) * 100
            if daily_loss_pct >= max_daily_loss_pct:
                log.warning(f"DAILY LOSS CAP breached for user {user_id}: {daily_loss_pct:.2f}%")
                halted = positions.halt_all_positions(user_id)
                activity.add_log(
                    user_id,
                    f"AUTO-HALT: Daily loss cap ({max_daily_loss_pct}%) breached. "
                    f"{halted} position(s) halted.",
                    level="ERROR",
                    category="RISK",
                )
                return

        # Max drawdown check
        max_dd_pct = float(risk.get("max_drawdown_pct", 6.0))
        if peak_equity > 0:
            current_dd = ((peak_equity - equity) / peak_equity) * 100
            if current_dd >= max_dd_pct:
                log.warning(f"MAX DRAWDOWN breached for user {user_id}: {current_dd:.2f}%")
                halted = positions.halt_all_positions(user_id)
                activity.add_log(
                    user_id,
                    f"AUTO-HALT: Max drawdown ({max_dd_pct}%) breached. "
                    f"{halted} position(s) halted.",
                    level="ERROR",
                    category="RISK",
                )

    async def _auto_close(self, user_id: str, position_id: str, price: float, reason: str):
        """Auto-close a position due to SL/TP hit."""
        from .trading_engine import trading_engine
        try:
            trading_engine.close_paper_position(
                user_id=user_id,
                position_id=position_id,
                close_price=price,
                reason=reason,
            )
        except Exception as e:
            log.error(f"Auto-close failed for {position_id}: {e}")
            activity.add_log(
                user_id,
                f"Auto-close failed for position {position_id[:8]}: {e}",
                level="ERROR",
                category="RISK",
            )


# Module-level singleton
risk_worker = RiskWorker()
