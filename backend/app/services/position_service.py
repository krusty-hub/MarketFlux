"""
MarketFlux – Position Service
Lifecycle management for paper-trading positions (open, close, update P&L).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase

log = logging.getLogger("marketflux.position_service")


# ═══════════════════════════════════════════════════════════════════════════════
#  POSITION QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_open_positions(user_id: str) -> List[Dict[str, Any]]:
    """Fetch all OPEN positions for a user."""
    sb = get_supabase()
    result = (
        sb.table("positions")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "OPEN")
        .order("entry_time", desc=True)
        .execute()
    )
    return result.data or []


def get_all_positions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch all positions (open + closed) for a user, most recent first."""
    sb = get_supabase()
    result = (
        sb.table("positions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_position_by_id(position_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single position by its ID."""
    sb = get_supabase()
    result = sb.table("positions").select("*").eq("id", position_id).execute()
    if result.data:
        pos = result.data[0]
        pos["_table"] = "positions"
        return pos
        
    result2 = sb.table("paper_trades").select("*").eq("id", position_id).execute()
    if result2.data:
        pos = result2.data[0]
        pos["_table"] = "paper_trades"
        pos["size"] = pos.get("position_size", 0)
        pos["notional_value"] = 0.0
        pos["current_price"] = pos.get("entry_price", 0)
        return pos
        
    return None


def count_open_positions(user_id: str) -> int:
    """Count the number of currently open positions for a user."""
    positions = get_open_positions(user_id)
    return len(positions)


# ═══════════════════════════════════════════════════════════════════════════════
#  POSITION LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

def open_position(
    user_id: str,
    symbol: str,
    direction: str,
    entry_price: float,
    size: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Open a new paper-trading position.
    Inserts into the positions table and returns the new row.
    """
    sb = get_supabase()

    direction = direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"Invalid direction: {direction}. Must be 'LONG' or 'SHORT'.")

    notional_value = entry_price * size

    position = {
        "user_id": user_id,
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "current_price": entry_price,
        "size": size,
        "notional_value": round(notional_value, 4),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "unrealized_pnl": 0.0,
        "status": "OPEN",
    }

    result = sb.table("positions").insert(position).execute()
    if result.data:
        log.info(
            f"Opened {direction} {symbol} position for user {user_id}: "
            f"size={size}, entry=${entry_price:,.2f}"
        )
        return result.data[0]
    raise RuntimeError("Failed to insert position into database.")


def close_position(
    position_id: str,
    close_price: float,
    reason: str = "MANUAL",
) -> Dict[str, Any]:
    """
    Close an open position.
    Calculates realized P&L and marks as CLOSED.
    """
    sb = get_supabase()

    pos = get_position_by_id(position_id)
    if not pos:
        raise ValueError(f"Position {position_id} not found.")

    table = pos.pop("_table", "positions")

    if pos["status"] != "OPEN":
        raise ValueError(f"Position {position_id} is already {pos['status']}.")

    entry_price = float(pos["entry_price"])
    size = float(pos["size"])
    direction = pos.get("direction", "LONG").upper()

    # Calculate realized P&L
    if direction in ("LONG", "BUY"):
        realized_pnl = (close_price - entry_price) * size
    else:  # SHORT
        realized_pnl = (entry_price - close_price) * size

    now = datetime.now(timezone.utc).isoformat()

    if table == "positions":
        updates = {
            "status": "CLOSED",
            "current_price": close_price,
            "realized_pnl": round(realized_pnl, 4),
            "unrealized_pnl": 0.0,
            "close_reason": reason,
            "close_time": now,
            "updated_at": now,
        }
    else:
        updates = {
            "status": "CLOSED",
            "realized_pnl": round(realized_pnl, 4),
        }

    result = sb.table(table).update(updates).eq("id", position_id).execute()
    if result.data:
        log.info(
            f"Closed position {position_id} ({direction} {pos['symbol']}) "
            f"at ${close_price:,.2f}, P&L: ${realized_pnl:+,.2f} ({reason})"
        )
        return result.data[0]
    raise RuntimeError(f"Failed to close position {position_id}.")


def update_position_price(position_id: str, current_price: float) -> Dict[str, Any]:
    """
    Update the current price and unrealized P&L of an open position.
    Called by the price feed service whenever new prices arrive.
    """
    sb = get_supabase()

    pos = get_position_by_id(position_id)
    if not pos or pos["status"] != "OPEN":
        return pos or {}

    entry_price = float(pos["entry_price"])
    size = float(pos["size"])
    direction = pos["direction"]

    # Calculate unrealized P&L
    if direction == "LONG":
        unrealized_pnl = (current_price - entry_price) * size
    else:  # SHORT
        unrealized_pnl = (entry_price - current_price) * size

    updates = {
        "current_price": current_price,
        "unrealized_pnl": round(unrealized_pnl, 4),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    result = sb.table("positions").update(updates).eq("id", position_id).execute()
    return result.data[0] if result.data else pos


def update_all_positions_price(user_id: str, symbol: str, current_price: float) -> List[Dict[str, Any]]:
    """
    Bulk update all open positions for a given symbol with the latest price.
    Returns the updated positions.
    """
    positions = get_open_positions(user_id)
    updated = []
    for pos in positions:
        if pos["symbol"] == symbol:
            u = update_position_price(pos["id"], current_price)
            updated.append(u)
    return updated


def halt_all_positions(user_id: str) -> int:
    """Emergency halt — mark all open positions as HALTED."""
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    positions = get_open_positions(user_id)
    count = 0
    for pos in positions:
        sb.table("positions").update({
            "status": "HALTED",
            "close_reason": "EMERGENCY_HALT",
            "close_time": now,
            "updated_at": now,
        }).eq("id", pos["id"]).execute()
        count += 1
    log.warning(f"Emergency halted {count} positions for user {user_id}")
    return count


def calculate_total_unrealized_pnl(user_id: str) -> float:
    """Sum the unrealized P&L across all open positions."""
    positions = get_open_positions(user_id)
    return sum(float(p.get("unrealized_pnl", 0.0)) for p in positions)
