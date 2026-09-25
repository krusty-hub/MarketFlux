"""
MarketFlux – Bot Control Center & Risk Management Service
Database-backed bot state management. Bridges the frontend UI with the
paper-trading engine, portfolio service, and live price feed.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import portfolio_service as portfolio
from . import position_service as positions
from . import activity_log_service as activity
from .price_feed import price_feed
from .trading_engine import trading_engine

log = logging.getLogger("marketflux.bot_service")


class BotService:
    """
    Singleton service that manages bot lifecycle (start/pause/stop/halt),
    mode switching, and orchestrates the trading engine.
    Now backed by Supabase instead of in-memory state.
    """
    _instance: Optional[BotService] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(BotService, cls).__new__(cls)
                    cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        # Bot lifecycle state (kept in memory — not per-user for simplicity)
        self.status = "ONLINE"  # ONLINE | PAUSED | STOPPED | EMERGENCY_HALTED
        self.strategy_name = "SMC Liquidity & Institutional Confluence v3.0"
        self.active_model_id = "BTCUSDT_5m"

    # ─────────────────────────────────────────────────────────────────────────
    #  STATUS
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build the complete bot status response.
        If user_id is provided, fetches real data from the database.
        Otherwise falls back to in-memory defaults for unauthenticated views.
        """
        if user_id:
            return self._get_db_status(user_id)
        return self._get_fallback_status()

    def _get_db_status(self, user_id: str) -> Dict[str, Any]:
        """Build status from database-backed data."""
        port = portfolio.get_or_create_portfolio(user_id)
        risk = portfolio.get_risk_settings(user_id)
        open_pos = positions.get_open_positions(user_id)
        logs = activity.get_recent_logs(user_id, limit=30)

        paper_balance = float(port.get("paper_balance", 10000.0))
        equity = float(port.get("equity", 10000.0))
        today_pnl = float(port.get("today_pnl", 0.0))
        total_pnl = float(port.get("total_pnl", 0.0))
        win_count = int(port.get("win_count", 0))
        loss_count = int(port.get("loss_count", 0))
        peak_equity = float(port.get("peak_equity", 10000.0))

        # Calculate derived stats
        total_trades = win_count + loss_count
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
        today_pnl_pct = (today_pnl / paper_balance * 100) if paper_balance > 0 else 0.0
        drawdown = ((peak_equity - equity) / peak_equity * 100) if peak_equity > 0 else 0.0

        # Format positions for frontend
        formatted_positions = []
        for p in open_pos:
            entry_price = float(p.get("entry_price", 0))
            current_price = float(p.get("current_price", entry_price))
            unrealized_pnl = float(p.get("unrealized_pnl", 0))
            notional = float(p.get("notional_value", 0))
            pnl_pct = (unrealized_pnl / notional * 100) if notional > 0 else 0.0

            formatted_positions.append({
                "id": p["id"][:8] if p.get("id") else "???",
                "full_id": p.get("id"),
                "symbol": p.get("symbol", "???"),
                "side": p.get("direction", "LONG"),
                "entry_price": entry_price,
                "current_price": current_price,
                "amount": float(p.get("size", 0)),
                "stop_loss": float(p["stop_loss"]) if p.get("stop_loss") else None,
                "take_profit": float(p["take_profit"]) if p.get("take_profit") else None,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "entry_time": p.get("entry_time", ""),
                "status": p.get("status", "OPEN"),
            })

        # Get live prices for display
        prices = price_feed.prices

        return {
            "status": self.status,
            "mode": port.get("mode", "paper"),
            "strategy_name": self.strategy_name,
            "active_model_id": self.active_model_id,
            "balance": round(paper_balance, 2),
            "equity": round(equity, 2),
            "today_pnl": round(today_pnl, 2),
            "today_pnl_pct": round(today_pnl_pct, 2),
            "win_rate": round(win_rate, 1),
            "drawdown": round(drawdown, 1),
            "trades_today": total_trades,
            "total_pnl": round(total_pnl, 2),
            "open_positions": formatted_positions,
            "risk_config": {
                "max_daily_loss_pct": float(risk.get("max_daily_loss_pct", 4.0)),
                "max_drawdown_pct": float(risk.get("max_drawdown_pct", 6.0)),
                "risk_per_trade_pct": float(risk.get("risk_per_trade_pct", 1.5)),
                "max_open_positions": int(risk.get("max_open_positions", 3)),
                "max_position_size_usd": float(risk.get("max_position_size_usd", 2500.0)),
                "stop_loss_atr": float(risk.get("stop_loss_atr", 1.5)),
                "take_profit_rr": float(risk.get("take_profit_rr", 2.0)),
                "trading_session": risk.get("trading_session", "ANY"),
                "consecutive_loss_limit": int(risk.get("consecutive_loss_limit", 3)),
            },
            "recent_logs": logs,
            "live_prices": {k: round(v, 2) for k, v in prices.items()},
            "price_feed_active": price_feed._running,
        }

    def _get_fallback_status(self) -> Dict[str, Any]:
        """Fallback status when no user is authenticated."""
        return {
            "status": self.status,
            "mode": "paper",
            "strategy_name": self.strategy_name,
            "active_model_id": self.active_model_id,
            "balance": 10000.0,
            "equity": 10000.0,
            "today_pnl": 0.0,
            "today_pnl_pct": 0.0,
            "win_rate": 0.0,
            "drawdown": 0.0,
            "trades_today": 0,
            "total_pnl": 0.0,
            "open_positions": [],
            "risk_config": portfolio.DEFAULT_RISK_CONFIG,
            "recent_logs": [],
            "live_prices": {},
            "price_feed_active": price_feed._running,
        }

    # ─────────────────────────────────────────────────────────────────────────
    #  CONTROLS
    # ─────────────────────────────────────────────────────────────────────────

    def set_control(self, action: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Handle bot lifecycle actions: START, PAUSE, STOP, EMERGENCY_KILL."""
        action = action.upper()

        if action == "START":
            self.status = "ONLINE"
            if user_id:
                activity.add_log(user_id, "Bot execution loop started.", "SUCCESS", "ENGINE")
                # Register user for risk monitoring
                from .risk_worker import risk_worker
                risk_worker.register_user(user_id)

        elif action == "PAUSE":
            self.status = "PAUSED"
            if user_id:
                activity.add_log(user_id, "Bot paused by user.", "WARN", "ENGINE")

        elif action == "STOP":
            self.status = "STOPPED"
            if user_id:
                activity.add_log(user_id, "Bot execution stopped.", "INFO", "ENGINE")
                from .risk_worker import risk_worker
                risk_worker.unregister_user(user_id)

        elif action == "EMERGENCY_KILL":
            self.status = "EMERGENCY_HALTED"
            if user_id:
                halted_count = positions.halt_all_positions(user_id)
                activity.add_log(
                    user_id,
                    f"EMERGENCY KILL SWITCH ACTIVATED. {halted_count} position(s) halted.",
                    "ERROR",
                    "ENGINE",
                )
                from .risk_worker import risk_worker
                risk_worker.unregister_user(user_id)
        else:
            raise ValueError(f"Unknown action: {action}")

        return self.get_status(user_id)

    def set_mode(
        self,
        new_mode: str,
        user_id: Optional[str] = None,
        confirmation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Switch between paper and live trading mode."""
        new_mode = new_mode.lower()

        if new_mode == "live":
            if confirmation != "CONFIRM LIVE":
                raise ValueError("Live trading requires explicit typing of 'CONFIRM LIVE'.")
            if user_id:
                portfolio.set_portfolio_mode(user_id, "live")
                activity.add_log(
                    user_id,
                    "CAUTION: Live Trading execution enabled by user.",
                    "WARN",
                    "ENGINE",
                )
        else:
            if user_id:
                portfolio.set_portfolio_mode(user_id, "paper")
                activity.add_log(
                    user_id,
                    "Switched to Paper Trading simulation mode.",
                    "INFO",
                    "ENGINE",
                )

        return self.get_status(user_id)

    def update_risk_config(self, new_config: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """Update risk management parameters."""
        if user_id:
            portfolio.update_risk_settings(user_id, new_config)
            activity.add_log(user_id, "Risk parameters updated successfully.", "INFO", "ENGINE")
        return self.get_status(user_id)

    # ─────────────────────────────────────────────────────────────────────────
    #  TRADE EXECUTION (delegates to trading_engine)
    # ─────────────────────────────────────────────────────────────────────────

    def execute_trade(
        self,
        user_id: str,
        symbol: str,
        direction: str,
        entry_price: Optional[float] = None,
        size: Optional[float] = None,
        notional_usd: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a paper trade through the trading engine."""
        if self.status in ("STOPPED", "EMERGENCY_HALTED"):
            raise ValueError(f"Bot is {self.status}. Cannot execute trades.")
        if self.status == "PAUSED":
            raise ValueError("Bot is PAUSED. Resume before executing trades.")

        return trading_engine.execute_paper_trade(
            user_id=user_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            size=size,
            notional_usd=notional_usd,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def close_position(
        self,
        user_id: str,
        position_id: str,
        close_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Close an open position."""
        return trading_engine.close_paper_position(
            user_id=user_id,
            position_id=position_id,
            close_price=close_price,
            reason="MANUAL",
        )
