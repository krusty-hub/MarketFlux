"""
Bot Control API Routes
Manages bot lifecycle (start/pause/stop), safety paper/live mode toggles, and risk configuration.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.bot_service import BotService

log = logging.getLogger("marketflux.routes.bot")
router = APIRouter()
bot_service = BotService()


class ControlRequest(BaseModel):
    action: str = Field(description="START | PAUSE | STOP | EMERGENCY_KILL")


class ModeRequest(BaseModel):
    mode: str = Field(description="paper | live")
    confirmation: Optional[str] = Field(default=None, description="Must be 'CONFIRM LIVE' for live mode")


class RiskConfigRequest(BaseModel):
    max_daily_loss_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    risk_per_trade_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_position_size_usd: Optional[float] = None
    stop_loss_atr: Optional[float] = None
    take_profit_rr: Optional[float] = None
    trading_session: Optional[str] = None
    consecutive_loss_limit: Optional[int] = None


@router.get("/status")
def get_bot_status():
    """Get complete status of trading bot, risk parameters, and open positions."""
    return bot_service.get_status()


@router.post("/control")
def set_control(req: ControlRequest):
    """Start, pause, stop, or emergency kill the trading bot."""
    try:
        return bot_service.set_control(req.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode")
def set_mode(req: ModeRequest):
    """Switch between Paper Trading and Live Trading (with strict safety confirmation)."""
    try:
        return bot_service.set_mode(req.mode, req.confirmation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-config")
def update_risk(req: RiskConfigRequest):
    """Update risk management parameters."""
    try:
        valid_updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return bot_service.update_risk_config(valid_updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
