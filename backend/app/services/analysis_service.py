"""
MarketFlux – Analysis Service
Queries the trades table and surfaces performance insights grouped by condition.
This feeds the periodic retraining decision process.
"""
from __future__ import annotations

import logging
from typing import List

log = logging.getLogger("marketflux.analysis")


def get_performance_stats(symbol: str = None, timeframe: str = None) -> dict:
    """
    Calculate overall performance stats from the trades table.
    Returns aggregated win/loss/BE counts, win rate, and top performing conditions.
    """
    try:
        from ..services.evaluation_service import get_supabase_client
        client = get_supabase_client()

        query = client.table("trades").select("*").not_.is_("actual_outcome", "null")
        if symbol:
            query = query.eq("pair", symbol)
        if timeframe:
            query = query.eq("timeframe", timeframe)

        resp  = query.execute()
        trades = resp.data or []

        if not trades:
            return {"total_signals": 0, "message": "No evaluated trades yet."}

        wins  = [t for t in trades if t["actual_outcome"] == "WIN"]
        losses= [t for t in trades if t["actual_outcome"] == "LOSS"]
        bes   = [t for t in trades if t["actual_outcome"] == "BE"]

        total     = len(trades)
        win_rate  = len(wins) / total if total > 0 else 0.0
        buy_sigs  = sum(1 for t in trades if t["direction"] == "BUY")
        sell_sigs = sum(1 for t in trades if t["direction"] == "SELL")

        gross_profit = sum(t["pnl"] for t in wins  if t.get("pnl") is not None)
        gross_loss   = abs(sum(t["pnl"] for t in losses if t.get("pnl") is not None))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        top_conditions = _analyze_conditions(trades)

        return {
            "total_signals":   total,
            "wins":            len(wins),
            "losses":          len(losses),
            "breakevens":      len(bes),
            "win_rate":        round(win_rate, 4),
            "profit_factor":   round(profit_factor, 3),
            "avg_error_pct":   0.0,
            "buy_signals":     buy_sigs,
            "sell_signals":    sell_sigs,
            "top_conditions":  top_conditions,
        }

    except Exception as e:
        log.error(f"Performance stats failed: {e}")
        return {"error": str(e)}


def _analyze_conditions(trades: List[dict]) -> List[dict]:
    """
    Group trades by SMC condition combinations and calculate win rates per group.
    Returns top conditions sorted by win rate (min 5 samples).
    """
    from collections import defaultdict

    groups: dict = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})

    condition_keys = ["session", "liquidity_sweep", "bos", "choch", "order_block", "fvg", "market_regime"]

    for trade in trades:
        # Build a readable condition label
        parts = []
        for key in condition_keys:
            val = trade.get(key)
            if val is True:
                parts.append(key)
            elif isinstance(val, str) and val not in ("", "null", "None"):
                parts.append(val)
        label = " + ".join(parts) if parts else "no_conditions"

        groups[label]["count"] += 1
        if trade["actual_outcome"] == "WIN":
            groups[label]["wins"] += 1
        if trade.get("pnl") is not None:
            groups[label]["pnl"] += float(trade["pnl"])

    results = []
    for condition, data in groups.items():
        count = data["count"]
        if count < 5:
            continue
        win_rate = data["wins"] / count
        results.append({
            "condition":    condition,
            "sample_count": count,
            "win_rate":     round(win_rate, 4),
            "avg_pnl":      round(data["pnl"] / count, 5),
        })

    # Sort by win rate descending
    return sorted(results, key=lambda x: x["win_rate"], reverse=True)[:10]


def get_error_breakdown(symbol: str = None) -> dict:
    """Return counts of each error_type from losing trades."""
    try:
        from ..services.evaluation_service import get_supabase_client
        client = get_supabase_client()
        query = client.table("trades").select("error_type").eq("actual_outcome", "LOSS")
        if symbol:
            query = query.eq("pair", symbol)
        resp = query.execute()

        from collections import Counter
        counts = Counter(t.get("error_type", "unknown") for t in (resp.data or []))
        return dict(counts.most_common())

    except Exception as e:
        log.error(f"Error breakdown failed: {e}")
        return {"error": str(e)}
