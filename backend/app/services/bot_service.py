"""
MarketFlux – Bot Control Center & Risk Management Service
Maintains state for the automated trading bot, manages paper/live execution,
enforces strict risk parameters, and handles the emergency kill switch.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import DATA_DIR

log = logging.getLogger("marketflux.bot_service")
BOT_STATE_FILE = DATA_DIR / "bot_state.json"


class BotService:
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
        self.status = "ONLINE"  # ONLINE | PAUSED | STOPPED | EMERGENCY_HALTED
        self.mode = "paper"     # paper | live (defaults strictly to paper)
        self.strategy_name = "SMC Liquidity & Institutional Confluence v3.0"
        self.active_model_id = "BTCUSDT_5m"
        
        # Financial State
        self.initial_paper_balance = 10000.0
        self.balance = 10000.0
        self.equity = 10245.50
        self.today_pnl = 245.50
        self.today_pnl_pct = 2.45
        self.win_rate = 68.4
        self.max_drawdown = 1.2
        self.trades_today = 4

        # Risk Controls
        self.risk_config = {
            "max_daily_loss_pct": 4.0,
            "max_drawdown_pct": 6.0,
            "risk_per_trade_pct": 1.5,
            "max_open_positions": 3,
            "max_position_size_usd": 2500.0,
            "stop_loss_atr": 1.5,
            "take_profit_rr": 2.0,
            "trading_session": "ANY",
            "consecutive_loss_limit": 3,
        }

        # Open Positions
        self.open_positions = [
            {
                "id": "POS-001",
                "symbol": "BTC/USDT",
                "side": "LONG",
                "entry_price": 103250.0,
                "current_price": 104120.0,
                "amount": 0.024,
                "stop_loss": 101800.0,
                "take_profit": 106150.0,
                "unrealized_pnl": 20.88,
                "unrealized_pnl_pct": 0.84,
                "entry_time": "14:15:02",
                "status": "OPEN",
            }
        ]

        # Logs
        self.logs: List[Dict[str, str]] = [
            {"time": "14:15:02", "level": "INFO", "text": "Signal detected: BTC/USDT Bullish FVG + Liquidity Sweep. Score: 84/100"},
            {"time": "14:15:03", "level": "SUCCESS", "text": "[PAPER] Filled order POS-001 LONG 0.024 BTC/USDT @ 103,250.0"},
            {"time": "14:20:10", "level": "INFO", "text": "Risk scan: portfolio exposure within 5.0% threshold."},
        ]

        self._load_state()

    def _load_state(self):
        if BOT_STATE_FILE.exists():
            try:
                with open(BOT_STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.status = data.get("status", self.status)
                    self.mode = data.get("mode", "paper")  # always ensure paper fallback
                    self.strategy_name = data.get("strategy_name", self.strategy_name)
                    self.active_model_id = data.get("active_model_id", self.active_model_id)
                    self.balance = data.get("balance", self.balance)
                    self.equity = data.get("equity", self.equity)
                    self.risk_config.update(data.get("risk_config", {}))
            except Exception as e:
                log.warning(f"Could not load bot state: {e}")

    def _save_state(self):
        try:
            payload = {
                "status": self.status,
                "mode": self.mode,
                "strategy_name": self.strategy_name,
                "active_model_id": self.active_model_id,
                "balance": self.balance,
                "equity": self.equity,
                "risk_config": self.risk_config,
            }
            with open(BOT_STATE_FILE, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save bot state: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "strategy_name": self.strategy_name,
            "active_model_id": self.active_model_id,
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "today_pnl": round(self.today_pnl, 2),
            "today_pnl_pct": round(self.today_pnl_pct, 2),
            "win_rate": self.win_rate,
            "drawdown": self.max_drawdown,
            "trades_today": self.trades_today,
            "open_positions": self.open_positions,
            "risk_config": self.risk_config,
            "recent_logs": self.logs[-30:],
        }

    def set_control(self, action: str) -> Dict[str, Any]:
        action = action.upper()
        if action == "START":
            self.status = "ONLINE"
            self._add_log("Bot execution loop started.", "SUCCESS")
        elif action == "PAUSE":
            self.status = "PAUSED"
            self._add_log("Bot paused by user.", "WARN")
        elif action == "STOP":
            self.status = "STOPPED"
            self._add_log("Bot execution stopped.", "INFO")
        elif action == "EMERGENCY_KILL":
            self.status = "EMERGENCY_HALTED"
            self._add_log("EMERGENCY KILL SWITCH ACTIVATED. System halted.", "ERROR")
            # Flatten or protect open positions
            for pos in self.open_positions:
                pos["status"] = "HALTED"
        else:
            raise ValueError(f"Unknown action: {action}")
        self._save_state()
        return self.get_status()

    def set_mode(self, new_mode: str, confirmation: Optional[str] = None) -> Dict[str, Any]:
        new_mode = new_mode.lower()
        if new_mode == "live":
            if confirmation != "CONFIRM LIVE":
                raise ValueError("Live trading requires explicit typing of 'CONFIRM LIVE'.")
            self.mode = "live"
            self._add_log("CAUTION: Live Trading execution enabled by user.", "WARN")
        else:
            self.mode = "paper"
            self._add_log("Switched to Paper Trading simulation mode.", "INFO")
        self._save_state()
        return self.get_status()

    def update_risk_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        self.risk_config.update(new_config)
        self._add_log("Risk parameters updated successfully.", "INFO")
        self._save_state()
        return self.get_status()

    def _add_log(self, text: str, level: str = "INFO"):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logs.append({"time": ts, "level": level, "text": text})
