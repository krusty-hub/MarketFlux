"""
Signals / Performance Routes
GET /api/signals/history
GET /api/signals/performance
GET /api/signals/errors
"""
import logging
from fastapi import APIRouter, Query, HTTPException

from ...services.analysis_service import get_performance_stats, get_error_breakdown

log = logging.getLogger("marketflux.routes.signals")
router = APIRouter()


@router.get("/history")
def get_signal_history(
    symbol:      str = Query(None, description="Filter by symbol, e.g. BTCUSDT"),
    timeframe:   str = Query(None, description="Filter by timeframe, e.g. 5m"),
    limit:       int = Query(50, ge=1, le=500),
    outcome:     str = Query(None, description="WIN | LOSS | BE"),
):
    """Return historical signals from Supabase trades table."""
    try:
        from ...services.evaluation_service import get_supabase_client
        client = get_supabase_client()

        query = client.table("trades").select("*").order("timestamp", desc=True).limit(limit)
        if symbol:
            query = query.eq("pair", symbol.upper())
        if timeframe:
            query = query.eq("timeframe", timeframe)
        if outcome:
            query = query.eq("actual_outcome", outcome.upper())

        resp = query.execute()
        return {"count": len(resp.data), "trades": resp.data or []}

    except Exception as e:
        log.error(f"Signal history error: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch signal history.")


@router.get("/performance")
def get_performance(
    symbol:    str = Query(None),
    timeframe: str = Query(None),
):
    """Return aggregated win/loss stats and top-performing conditions."""
    stats = get_performance_stats(symbol=symbol, timeframe=timeframe)
    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])
    return stats


@router.get("/errors")
def get_error_analysis(symbol: str = Query(None)):
    """Return breakdown of error types from losing trades."""
    breakdown = get_error_breakdown(symbol=symbol)
    if "error" in breakdown:
        raise HTTPException(status_code=500, detail=breakdown["error"])
    return {"error_types": breakdown}


@router.get("/model-versions")
def get_model_versions(symbol: str = Query(None)):
    """Return all model versions and their performance metrics."""
    try:
        from ...services.evaluation_service import get_supabase_client
        client = get_supabase_client()
        query = client.table("model_versions").select("*").order("training_date", desc=True)
        if symbol:
            query = query.eq("symbol", symbol.upper())
        resp = query.execute()
        return {"versions": resp.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch model versions: {e}")
