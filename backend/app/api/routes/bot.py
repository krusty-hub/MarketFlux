"""
Bot Control API Routes
Manages bot lifecycle, paper trading execution, portfolio, positions,
risk configuration, and real-time WebSocket price/P&L streaming.
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel, Field

from ...services.bot_service import BotService
from ...services.price_feed import price_feed
from ...services import position_service as positions
from ...services import portfolio_service as portfolio
from ...services import activity_log_service as activity
from ...core.auth import get_current_user, get_optional_user

log = logging.getLogger("marketflux.routes.bot")
router = APIRouter()
bot_service = BotService()


# ── Request Schemas ───────────────────────────────────────────────────────────

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


class ExecuteTradeRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair, e.g. 'BTC/USDT'")
    direction: str = Field(..., description="LONG or SHORT")
    entry_price: Optional[float] = Field(default=None, description="Entry price (uses live price if omitted)")
    size: Optional[float] = Field(default=None, description="Position size in asset units")
    notional_usd: Optional[float] = Field(default=None, description="Position size in USD (alternative to size)")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price")
    take_profit: Optional[float] = Field(default=None, description="Take profit price")


class ClosePositionRequest(BaseModel):
    close_price: Optional[float] = Field(default=None, description="Close price (uses live price if omitted)")


# ── Bot Status ────────────────────────────────────────────────────────────────

@router.get("/status")
def get_bot_status(user: Optional[Dict] = Depends(get_optional_user)):
    """Get complete status of trading bot, portfolio, risk parameters, and open positions."""
    user_id = user["id"] if user else None
    return bot_service.get_status(user_id)


# ── Bot Controls ──────────────────────────────────────────────────────────────

@router.post("/control")
def set_control(req: ControlRequest, user: Optional[Dict] = Depends(get_optional_user)):
    """Start, pause, stop, or emergency kill the trading bot."""
    try:
        user_id = user["id"] if user else None
        return bot_service.set_control(req.action, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode")
def set_mode(req: ModeRequest, user: Optional[Dict] = Depends(get_optional_user)):
    """Switch between Paper Trading and Live Trading (with strict safety confirmation)."""
    try:
        user_id = user["id"] if user else None
        return bot_service.set_mode(req.mode, user_id, req.confirmation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/risk-config")
def update_risk(req: RiskConfigRequest, user: Optional[Dict] = Depends(get_optional_user)):
    """Update risk management parameters."""
    try:
        user_id = user["id"] if user else None
        valid_updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return bot_service.update_risk_config(valid_updates, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Trade Execution ──────────────────────────────────────────────────────────

@router.post("/execute")
def execute_trade(req: ExecuteTradeRequest, user: Optional[Dict] = Depends(get_optional_user)):
    """
    Execute a paper trade. The engine validates risk rules, deducts margin,
    and opens a position in the database.
    """
    user_id = user["id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required for trading.")
    try:
        result = bot_service.execute_trade(
            user_id=user_id,
            symbol=req.symbol,
            direction=req.direction,
            entry_price=req.entry_price,
            size=req.size,
            notional_usd=req.notional_usd,
            stop_loss=req.stop_loss,
            take_profit=req.take_profit,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Trade execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position/{position_id}")
def close_position(position_id: str, req: ClosePositionRequest = ClosePositionRequest(), user: Optional[Dict] = Depends(get_optional_user)):
    """Close an active paper trading position."""
    user_id = user["id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        result = bot_service.close_position(
            user_id=user_id,
            position_id=position_id,
            close_price=req.close_price,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Close position error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Portfolio & Positions ────────────────────────────────────────────────────

@router.get("/portfolio")
def get_portfolio(user: Optional[Dict] = Depends(get_optional_user)):
    """Fetch the user's portfolio balance and equity."""
    user_id = user["id"] if user else None
    if not user_id:
        return {
            "paper_balance": 10000.0,
            "equity": 10000.0,
            "mode": "paper",
            "today_pnl": 0.0,
            "total_pnl": 0.0,
        }
    port = portfolio.get_or_create_portfolio(user_id)
    return port


@router.post("/portfolio/reset")
def reset_portfolio(user: Dict = Depends(get_current_user)):
    """Reset paper balance back to $10,000."""
    try:
        # Close all open positions first
        open_pos = positions.get_open_positions(user["id"])
        for pos in open_pos:
            positions.close_position(pos["id"], float(pos.get("current_price", pos["entry_price"])), "RESET")
        
        result = portfolio.reset_paper_balance(user["id"])
        activity.add_log(user["id"], "Paper balance reset to $10,000.00", "INFO", "ENGINE")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
def get_positions(user: Optional[Dict] = Depends(get_optional_user)):
    """List all open positions."""
    user_id = user["id"] if user else None
    if not user_id:
        return {"positions": []}
    pos = positions.get_open_positions(user_id)
    return {"positions": pos}


@router.get("/positions/history")
def get_position_history(limit: int = 50, user: Optional[Dict] = Depends(get_optional_user)):
    """List all positions (open + closed), most recent first."""
    user_id = user["id"] if user else None
    if not user_id:
        return {"positions": []}
    pos = positions.get_all_positions(user_id, limit)
    return {"positions": pos}


@router.get("/activity-logs")
def get_activity_logs(limit: int = 30, user: Optional[Dict] = Depends(get_optional_user)):
    """Fetch the trading engine activity feed."""
    user_id = user["id"] if user else None
    if not user_id:
        return {"logs": []}
    logs = activity.get_recent_logs(user_id, limit)
    return {"logs": logs}


# ── Price Feed Status ────────────────────────────────────────────────────────

@router.get("/price-feed")
def get_price_feed_status():
    """Get the current status of the Binance price feed."""
    return price_feed.get_status()


# ── WebSocket: Real-Time Price & P&L Stream ──────────────────────────────────

@router.websocket("/ws")
async def bot_websocket(ws: WebSocket):
    """
    WebSocket endpoint for real-time price updates and P&L streaming.
    Sends JSON messages every 2 seconds with:
    - Live prices from Binance
    - Updated position P&L
    - Portfolio equity
    """
    await ws.accept()
    log.info("WebSocket client connected")

    try:
        # Try to get user_id from query params (optional)
        user_id = ws.query_params.get("user_id")

        while True:
            payload: Dict[str, Any] = {
                "type": "price_update",
                "prices": {k: round(v, 2) for k, v in price_feed.prices.items()},
                "price_feed_active": price_feed._running,
            }

            # If user is identified, include portfolio data
            if user_id:
                try:
                    port = portfolio.get_or_create_portfolio(user_id)
                    open_pos = positions.get_open_positions(user_id)
                    unrealized = positions.calculate_total_unrealized_pnl(user_id)

                    paper_balance = float(port.get("paper_balance", 10000.0))
                    equity = paper_balance + unrealized

                    payload["portfolio"] = {
                        "paper_balance": round(paper_balance, 2),
                        "equity": round(equity, 2),
                        "today_pnl": round(float(port.get("today_pnl", 0.0)), 2),
                        "unrealized_pnl": round(unrealized, 2),
                    }

                    payload["positions"] = [
                        {
                            "id": p.get("id", "")[:8],
                            "full_id": p.get("id"),
                            "symbol": p.get("symbol"),
                            "direction": p.get("direction"),
                            "entry_price": float(p.get("entry_price", 0)),
                            "current_price": float(p.get("current_price", 0)),
                            "unrealized_pnl": round(float(p.get("unrealized_pnl", 0)), 2),
                            "status": p.get("status"),
                        }
                        for p in open_pos
                    ]
                except Exception as e:
                    log.debug(f"WebSocket portfolio error: {e}")

            await ws.send_json(payload)
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
    except Exception as e:
        log.warning(f"WebSocket error: {e}")
