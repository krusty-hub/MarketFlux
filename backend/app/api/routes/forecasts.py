"""
Forecast Routes
POST /api/forecasts/run
"""
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from ...data.crypto_provider import fetch_ohlcv as crypto_ohlcv, get_live_price
from ...data.forex_provider import fetch_dukascopy_ohlcv
from ...models.forecasting_engine import run_forecast
from ...services.evaluation_service import save_signal_to_supabase
from ...config.settings import CRYPTO_PAIRS, FOREX_PAIRS, CRYPTO_TIMEFRAMES

log = logging.getLogger("marketflux.routes.forecasts")
router = APIRouter()

# In-memory forecast state (one active forecast at a time per process)
_forecast_state: Dict = {
    "status":  "idle",   # idle | running | ready | error
    "result":  None,
    "error":   None,
    "symbol":  None,
    "started": None,
}
_lock = threading.Lock()


def _run_forecast_background(
    symbol: str,
    market_type: str,
    timeframe: str,
    exchange: str,
):
    """Background task: fetch data → features → inference → update state."""
    with _lock:
        _forecast_state["status"]  = "running"
        _forecast_state["result"]  = None
        _forecast_state["error"]   = None
        _forecast_state["symbol"]  = symbol
        _forecast_state["started"] = datetime.now(timezone.utc).isoformat()

    try:
        # Fetch data
        if market_type == "crypto":
            df = crypto_ohlcv(symbol, timeframe)
            live_price, price_source = get_live_price(symbol, exchange)
        else:
            df = fetch_dukascopy_ohlcv(symbol, timeframe)
            if df is None:
                raise RuntimeError(f"No forex data available for {symbol}")
            live_price  = float(df["close"].iloc[-1])
            price_source = "dukascopy"

        # Run forecast inference
        result = run_forecast(
            df_raw=df,
            symbol=symbol,
            market_type=market_type,
            timeframe=timeframe,
            live_price=live_price,
            price_source=price_source,
            exchange=exchange,
        )

        # Persist signal to Supabase immediately
        signal_id = save_signal_to_supabase(result)
        result["id"] = signal_id

        with _lock:
            _forecast_state["status"] = "ready"
            _forecast_state["result"] = result

        log.info(f"✓ Forecast complete for {symbol} {timeframe}: {result['signal']}")

    except Exception as e:
        log.error(f"Forecast background task failed: {e}", exc_info=True)
        with _lock:
            _forecast_state["status"] = "error"
            _forecast_state["error"]  = str(e)


@router.post("/run")
def run_forecast_endpoint(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"),
    market_type: str = Query("crypto"),
    timeframe: str = Query("5m"),
    exchange: str = Query("binance"),
):
    """
    Trigger a forecast run asynchronously.
    Poll /api/forecasts/status to get the result.
    """
    symbol = symbol.upper()

    with _lock:
        if _forecast_state["status"] == "running":
            raise HTTPException(status_code=409, detail="A forecast is already running.")

    # Validate inputs
    if market_type == "crypto" and symbol not in CRYPTO_PAIRS:
        raise HTTPException(status_code=400, detail=f"Unsupported crypto symbol: {symbol}")
    if market_type == "forex" and symbol not in FOREX_PAIRS:
        raise HTTPException(status_code=400, detail=f"Unsupported forex symbol: {symbol}")
    if market_type == "crypto" and timeframe not in CRYPTO_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}")

    background_tasks.add_task(
        _run_forecast_background, symbol, market_type, timeframe, exchange
    )
    return {"message": "Forecast started", "symbol": symbol, "timeframe": timeframe}


@router.get("/status")
def get_forecast_status():
    """Poll this endpoint to get the latest forecast state."""
    with _lock:
        return dict(_forecast_state)


@router.get("/latest")
def get_latest_forecast():
    """Return the most recent successful forecast result."""
    with _lock:
        if _forecast_state["status"] == "ready" and _forecast_state["result"]:
            return _forecast_state["result"]
        elif _forecast_state["status"] == "running":
            raise HTTPException(status_code=202, detail="Forecast still running.")
        elif _forecast_state["status"] == "error":
            raise HTTPException(status_code=500, detail=_forecast_state.get("error", "Unknown error"))
        else:
            raise HTTPException(status_code=404, detail="No forecast available. Run /api/forecasts/run first.")
