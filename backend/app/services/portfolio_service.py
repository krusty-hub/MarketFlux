"""
MarketFlux – Portfolio & Risk Settings Service
CRUD operations for the portfolios and risk_settings tables in Supabase.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .supabase_client import get_supabase

log = logging.getLogger("marketflux.portfolio_service")

INITIAL_PAPER_BALANCE = 10_000.0

# ── Default risk configuration ────────────────────────────────────────────────
DEFAULT_RISK_CONFIG = {
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


# ═══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_or_create_portfolio(user_id: str) -> Dict[str, Any]:
    """
    Fetch the user's portfolio. If none exists, initialize one with $10,000
    paper balance and default risk settings.
    """
    sb = get_supabase()

    # Try to fetch existing portfolio
    result = sb.table("portfolios").select("*").eq("user_id", user_id).execute()

    if result.data and len(result.data) > 0:
        return result.data[0]

    # Create new portfolio with initial paper balance
    new_portfolio = {
        "user_id": user_id,
        "paper_balance": INITIAL_PAPER_BALANCE,
        "equity": INITIAL_PAPER_BALANCE,
        "live_balance": 0.0,
        "mode": "paper",
        "total_pnl": 0.0,
        "today_pnl": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "peak_equity": INITIAL_PAPER_BALANCE,
    }
    insert_result = sb.table("portfolios").insert(new_portfolio).execute()
    portfolio = insert_result.data[0] if insert_result.data else new_portfolio

    # Also create default risk settings
    _ensure_risk_settings(user_id)

    log.info(f"Initialized portfolio for user {user_id}: ${INITIAL_PAPER_BALANCE}")
    return portfolio


def update_portfolio(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update portfolio fields (balance, equity, pnl, etc.)."""
    sb = get_supabase()
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = sb.table("portfolios").update(updates).eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]
    raise ValueError(f"Portfolio not found for user {user_id}")


def set_portfolio_mode(user_id: str, mode: str) -> Dict[str, Any]:
    """Switch between paper and live trading mode."""
    if mode not in ("paper", "live"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'paper' or 'live'.")
    return update_portfolio(user_id, {"mode": mode})


def reset_paper_balance(user_id: str) -> Dict[str, Any]:
    """Reset the paper balance back to $10,000 (fresh start)."""
    return update_portfolio(user_id, {
        "paper_balance": INITIAL_PAPER_BALANCE,
        "equity": INITIAL_PAPER_BALANCE,
        "total_pnl": 0.0,
        "today_pnl": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "peak_equity": INITIAL_PAPER_BALANCE,
    })


def update_equity(user_id: str, paper_balance: float, unrealized_pnl: float) -> Dict[str, Any]:
    """Recalculate and persist equity = paper_balance + unrealized_pnl."""
    equity = paper_balance + unrealized_pnl

    # Fetch current peak to track drawdown
    portfolio = get_or_create_portfolio(user_id)
    peak = max(portfolio.get("peak_equity", INITIAL_PAPER_BALANCE), equity)

    return update_portfolio(user_id, {
        "equity": round(equity, 4),
        "peak_equity": round(peak, 4),
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  RISK SETTINGS OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_risk_settings(user_id: str) -> Dict[str, Any]:
    """Create default risk settings if they don't exist."""
    sb = get_supabase()
    result = sb.table("risk_settings").select("*").eq("user_id", user_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]

    new_settings = {"user_id": user_id, **DEFAULT_RISK_CONFIG}
    insert_result = sb.table("risk_settings").insert(new_settings).execute()
    return insert_result.data[0] if insert_result.data else new_settings


def get_risk_settings(user_id: str) -> Dict[str, Any]:
    """Fetch risk settings for a user (creates defaults if missing)."""
    return _ensure_risk_settings(user_id)


def update_risk_settings(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update risk settings for a user."""
    sb = get_supabase()

    # Ensure risk settings exist
    _ensure_risk_settings(user_id)

    # Filter to only valid risk fields
    valid_fields = set(DEFAULT_RISK_CONFIG.keys())
    clean_updates = {k: v for k, v in updates.items() if k in valid_fields and v is not None}
    clean_updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("risk_settings").update(clean_updates).eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]
    raise ValueError(f"Risk settings not found for user {user_id}")


def check_risk_limits(user_id: str, trade_value: float, current_open_count: int) -> Dict[str, Any]:
    """
    Validate a proposed trade against the user's risk rules.
    Returns {"allowed": True/False, "reason": "..."}.
    """
    portfolio = get_or_create_portfolio(user_id)
    risk = get_risk_settings(user_id)

    equity = portfolio.get("equity", INITIAL_PAPER_BALANCE)
    today_pnl = portfolio.get("today_pnl", 0.0)
    peak_equity = portfolio.get("peak_equity", INITIAL_PAPER_BALANCE)

    # Check max open positions
    if current_open_count >= risk.get("max_open_positions", 3):
        return {"allowed": False, "reason": f"Max open positions ({risk['max_open_positions']}) reached."}

    # Check max position size
    max_size = risk.get("max_position_size_usd", 2500.0)
    if trade_value > max_size:
        return {"allowed": False, "reason": f"Trade value ${trade_value:.2f} exceeds max position size ${max_size:.2f}."}

    # Check daily loss cap
    max_daily_loss = equity * (risk.get("max_daily_loss_pct", 4.0) / 100.0)
    if today_pnl < 0 and abs(today_pnl) >= max_daily_loss:
        return {"allowed": False, "reason": f"Daily loss cap ({risk['max_daily_loss_pct']}%) breached."}

    # Check max drawdown
    max_dd_pct = risk.get("max_drawdown_pct", 6.0)
    if peak_equity > 0:
        current_dd = ((peak_equity - equity) / peak_equity) * 100
        if current_dd >= max_dd_pct:
            return {"allowed": False, "reason": f"Max drawdown ({max_dd_pct}%) breached. Current: {current_dd:.2f}%."}

    # Check risk per trade
    max_risk = equity * (risk.get("risk_per_trade_pct", 1.5) / 100.0)
    if trade_value > max_risk * 10:  # Rough leverage check (margin)
        return {"allowed": False, "reason": f"Trade exceeds risk-per-trade allocation."}

    return {"allowed": True, "reason": "All risk checks passed."}
