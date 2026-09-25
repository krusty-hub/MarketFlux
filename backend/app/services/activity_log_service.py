"""
MarketFlux – Activity Log Service
Writes and reads activity log entries to/from the Supabase activity_logs table.
Drives the "Trading Engine Activity Feed" in the frontend.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase

log = logging.getLogger("marketflux.activity_log_service")


def add_log(
    user_id: str,
    message: str,
    level: str = "INFO",
    category: str = "SYSTEM",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write an activity log entry to the database.
    
    Levels: INFO, SUCCESS, WARN, ERROR
    Categories: SYSTEM, TRADE, RISK, PRICE, ENGINE
    """
    sb = get_supabase()

    entry = {
        "user_id": user_id,
        "message": message,
        "level": level.upper(),
        "category": category.upper(),
        "metadata": metadata,
    }

    try:
        result = sb.table("activity_logs").insert(entry).execute()
        return result.data[0] if result.data else entry
    except Exception as e:
        log.warning(f"Failed to write activity log: {e}")
        return entry


def get_recent_logs(
    user_id: str,
    limit: int = 30,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch the most recent activity log entries for a user.
    Optionally filter by category.
    """
    sb = get_supabase()

    query = (
        sb.table("activity_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if category:
        query = query.eq("category", category.upper())

    result = query.execute()
    logs = result.data or []

    # Return in chronological order (oldest first) for the feed
    logs.reverse()

    # Format timestamps for frontend display
    for entry in logs:
        if entry.get("created_at"):
            try:
                dt = datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00"))
                entry["time"] = dt.strftime("%H:%M:%S")
            except (ValueError, AttributeError):
                entry["time"] = "00:00:00"
        entry.setdefault("time", "00:00:00")
        # Map 'message' to 'text' for frontend compatibility
        entry["text"] = entry.get("message", "")

    return logs
