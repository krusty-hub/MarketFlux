from fastapi import APIRouter
from datetime import datetime, timezone
from ...config.settings import CRYPTO_PAIRS, FOREX_PAIRS, CRYPTO_TIMEFRAMES

router = APIRouter()

@router.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "MarketFlux API",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "supported_crypto":   list(CRYPTO_PAIRS.keys()),
        "supported_forex":    list(FOREX_PAIRS.keys()),
        "supported_timeframes": CRYPTO_TIMEFRAMES,
    }
