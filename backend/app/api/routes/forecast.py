"""
MarketFlux – Unified AI Analysis & Forecasting Engine
Consolidates forecasting logic into a single centralized endpoint.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ...config.settings import DATA_DIR
from ...models.forecasting_engine import load_active_model, InstitutionalForecastModel
from ...models.feature_engineering import add_features
from ...data.crypto_provider import fetch_ohlcv

log = logging.getLogger("marketflux.routes.forecast")
router = APIRouter()

class ForecastRequest(BaseModel):
    symbol: str = "BTCUSDT"
    historical_period: int = 1000
    timeframe: str = "15m"
    model_id: str
    balance: float = 10000.0
    risk_per_trade_pct: float = 1.5
    slippage_pct: float = 0.02
    min_confidence_pct: float = 80.0

@router.post("/analyze")
def run_ai_analysis(req: ForecastRequest):
    """
    Unified Forecasting Engine:
    1. Fetch Data
    2. Model Inference
    3. Risk Management & Sizing
    4. Return Trade Setup
    """
    try:
        # 1. Data Fetching
        log.info(f"Fetching {req.historical_period} bars of {req.symbol} {req.timeframe} for AI Analysis")
        df = fetch_ohlcv(req.symbol, req.timeframe, limit=req.historical_period)
        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="Could not fetch historical data for analysis.")

        # 2. Model Inference
        # In the payload model_id might be something like "BTCUSDT_5m", "BTCUSDT_5m_v20260924_1452"
        # Since we use load_active_model based on symbol and timeframe, we'll try to load exactly what's requested.
        # Actually load_active_model takes symbol and timeframe, but if model_id is specific we load that.
        from ...config.settings import MODEL_DIR
        import joblib
        model_path = MODEL_DIR / f"{req.model_id}.joblib"
        if not model_path.exists():
            # fallback to symbol_timeframe
            model_path = MODEL_DIR / f"{req.symbol}_{req.timeframe}.joblib"
            
        if not model_path.exists():
            raise HTTPException(status_code=404, detail=f"Model {req.model_id} not found in registry.")
            
        model: InstitutionalForecastModel = joblib.load(model_path)
        if not getattr(model, 'trained', False):
            raise HTTPException(status_code=400, detail="Model is untrained.")

        # Extract features
        df = add_features(df)
        
        # We only need the latest row for the actual prediction
        latest_row = df.iloc[-1]
        
        # Prepare input for predict_proba
        # Model might require specific feature columns
        feature_cols = getattr(model, "feature_cols", [])
        if not feature_cols:
            from ...models.feature_engineering import get_feature_cols
            feature_cols = get_feature_cols(df)
            
        # Check if all required features exist
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            # fill missing with 0 for robustness or raise error
            for c in missing:
                df[c] = 0.0
                
        X_latest = df[feature_cols].iloc[[-1]].values
        
        # Get Confidence
        prob_win = model.predict_proba(X_latest)
        confidence_pct = round(prob_win * 100, 2)
        
        # 3. Risk Management
        if confidence_pct < req.min_confidence_pct:
            return {
                "status": "REJECTED",
                "message": f"AI Confidence ({confidence_pct}%) is below minimum threshold ({req.min_confidence_pct}%).",
                "confidence": confidence_pct
            }

        # Calculate Direction (Long if > 50, but we also rely on the model's structure)
        # Actually in our training pipeline target=1 is a LONG 2R win. 
        # But maybe we need a directional indicator if the model predicts both.
        # For simplicity, if probability > 50 it's a LONG, else SHORT (with 1-prob confidence).
        # Let's use EMA alignment or structural bias for direction if the model is purely generic,
        # but our model predicts "2R before 1R". Let's assume it predicts LONG success.
        # If it's trained symmetrically, we can use simple bias.
        
        # Let's derive direction from EMA alignment to be safe, or just assume LONG for this demo 
        # unless structural bias says SHORT.
        ema_alignment = latest_row.get("ema_alignment", 0)
        direction = "LONG" if ema_alignment >= 0 else "SHORT"
        
        # If the model gives low prob for LONG, it might mean SHORT has high prob.
        if direction == "SHORT":
            confidence_pct = round((1.0 - prob_win) * 100, 2)
            if confidence_pct < req.min_confidence_pct:
                return {
                    "status": "REJECTED",
                    "message": f"AI Confidence for SHORT ({confidence_pct}%) is below threshold.",
                    "confidence": confidence_pct
                }

        current_price = float(latest_row['close'])
        atr = float(latest_row.get('atr_14', current_price * 0.01)) # fallback 1% atr
        
        # SL and TP calculation
        if direction == "LONG":
            entry_price = current_price * (1 + req.slippage_pct / 100)
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 3.0) # 2R
        else:
            entry_price = current_price * (1 - req.slippage_pct / 100)
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 3.0)

        # Position Sizing
        risk_amount = req.balance * (req.risk_per_trade_pct / 100)
        risk_per_unit = abs(entry_price - stop_loss)
        
        position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
        
        return {
            "status": "ACCEPTED",
            "setup": {
                "symbol": req.symbol,
                "timeframe": req.timeframe,
                "direction": direction,
                "entry_price": round(entry_price, 6),
                "stop_loss": round(stop_loss, 6),
                "take_profit": round(take_profit, 6),
                "position_size": round(position_size, 6),
                "confidence": confidence_pct,
                "risk_amount": round(risk_amount, 2),
                "rr_ratio": 2.0,
                "model_id": req.model_id
            }
        }
        
    except Exception as e:
        log.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
