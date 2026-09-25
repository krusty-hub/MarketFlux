"""
MarketFlux – Trades Execution API
Receives a trade setup from the frontend, validates it, and pushes it to Supabase.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from supabase import create_client, Client
import os

log = logging.getLogger("marketflux.routes.trades")
router = APIRouter()

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase credentials not configured.")
    return create_client(url, key)


class TradeExecutionRequest(BaseModel):
    user_id: str
    symbol: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    ai_confidence: float
    model_id: str

@router.post("/execute")
def execute_trade(req: TradeExecutionRequest, supabase: Client = Depends(get_supabase)):
    """
    Pushes an AI-approved trade setup to the Supabase paper_trades table.
    """
    try:
        # Validate inputs
        if req.position_size <= 0:
            raise ValueError("Position size must be greater than 0")
        
        # Insert into Supabase
        payload = {
            "user_id": req.user_id,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "direction": req.direction,
            "entry_price": req.entry_price,
            "stop_loss": req.stop_loss,
            "take_profit": req.take_profit,
            "position_size": req.position_size,
            "ai_confidence": req.ai_confidence,
            "model_id": req.model_id,
            "status": "OPEN",
            "realized_pnl": 0.0
        }
        
        response = supabase.table("paper_trades").insert(payload).execute()
        
        if not response.data:
            raise Exception("Failed to insert trade, Supabase returned empty data.")
            
        trade_record = response.data[0]
        log.info(f"Trade successfully executed and saved: {trade_record['id']}")
        
        return {
            "message": "Trade executed successfully.",
            "trade": trade_record
        }
        
    except Exception as e:
        log.error(f"Trade execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

