"""
Market Data Routes
GET /api/market/{symbol}?timeframe=5m&market_type=crypto
"""
import logging
from fastapi import APIRouter, HTTPException, Query

from ...data.crypto_provider import fetch_ohlcv as crypto_ohlcv, get_live_price, get_supported_symbols
from ...data.forex_provider import fetch_dukascopy_ohlcv, get_forex_symbols
from ...config.settings import CRYPTO_PAIRS, FOREX_PAIRS, CRYPTO_TIMEFRAMES

log = logging.getLogger("marketflux.routes.market")
router = APIRouter()


@router.get("/symbols")
def list_symbols():
    """List all supported symbols grouped by market type."""
    return {
        "crypto": get_supported_symbols(),
        "forex":  get_forex_symbols(),
    }


@router.get("/{symbol}/price")
def get_price(
    symbol: str,
    market_type: str = Query("crypto", description="crypto or forex"),
    exchange: str = Query("binance"),
):
    """Fetch live price for a symbol."""
    try:
        if market_type == "crypto":
            price, source = get_live_price(symbol.upper(), exchange)
            return {"symbol": symbol.upper(), "price": price, "source": source}
        else:
            raise HTTPException(status_code=400, detail="Live forex prices via Dukascopy are not real-time. Use /ohlcv for historical data.")
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{symbol}/ohlcv")
def get_ohlcv(
    symbol: str,
    timeframe: str = Query("5m"),
    market_type: str = Query("crypto"),
    limit: int = Query(200, ge=50, le=1000),
):
    """Fetch OHLCV candles for a symbol."""
    symbol = symbol.upper()
    try:
        if market_type == "crypto":
            if symbol not in CRYPTO_PAIRS:
                raise HTTPException(status_code=404, detail=f"Unsupported crypto symbol: {symbol}")
            if timeframe not in CRYPTO_TIMEFRAMES:
                raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}")
            df = crypto_ohlcv(symbol, timeframe, limit)
        elif market_type == "forex":
            if symbol not in FOREX_PAIRS:
                raise HTTPException(status_code=404, detail=f"Unsupported forex symbol: {symbol}")
            df = fetch_dukascopy_ohlcv(symbol, timeframe, limit)
            if df is None:
                raise HTTPException(status_code=503, detail=f"Could not fetch forex data for {symbol}")
        else:
            raise HTTPException(status_code=400, detail="market_type must be 'crypto' or 'forex'")

        # Convert to JSON-serializable format
        records = [
            {
                "timestamp": str(idx),
                "open":   row.open,
                "high":   row.high,
                "low":    row.low,
                "close":  row.close,
                "volume": row.volume,
            }
            for idx, row in df.iterrows()
        ]
        return {
            "symbol":      symbol,
            "market_type": market_type,
            "timeframe":   timeframe,
            "count":       len(records),
            "candles":     records,
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error(f"OHLCV error ({symbol}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch market data.")
