"""
Backtest API Routes
Triggers real historical backtest simulations and returns equity curve metrics.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.backtest_service import run_backtest_simulation

log = logging.getLogger("marketflux.routes.backtest")
router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="5m")
    limit: int = Field(default=1000, ge=100, le=5000)
    starting_balance: float = Field(default=10000.0, ge=100.0)
    risk_per_trade_pct: float = Field(default=1.5, ge=0.1, le=10.0)
    spread: float = Field(default=1.0, ge=0.0)
    commission: float = Field(default=1.5, ge=0.0)
    slippage_pct: float = Field(default=0.02, ge=0.0, le=1.0)
    model_id: Optional[str] = None
    min_confidence: float = Field(default=0.60, ge=0.5, le=0.95)


@router.post("/run")
def execute_backtest(req: BacktestRequest):
    """Run an institutional backtest over real historical candles."""
    try:
        results = run_backtest_simulation(
            symbol=req.symbol,
            timeframe=req.timeframe,
            limit=req.limit,
            starting_balance=req.starting_balance,
            risk_per_trade_pct=req.risk_per_trade_pct,
            spread=req.spread,
            commission=req.commission,
            slippage_pct=req.slippage_pct,
            model_id=req.model_id,
            min_confidence=req.min_confidence,
        )
        return results
    except Exception as e:
        log.error(f"Backtest execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
