"""
MarketFlux – Application Settings
Loads configuration from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_env_path = Path(__file__).parents[4] / ".env"
load_dotenv(_env_path)

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Alpaca ────────────────────────────────────────────────────────────────────
ALPACA_URL: str = os.environ.get("ALPACA_URL", "https://paper-api.alpaca.markets/v2")
ALPACA_API_KEY: str = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY: str = os.environ.get("ALPACA_SECRET_KEY", "")

# ── API URLs ──────────────────────────────────────────────────────────────────
BINANCE_KLINES_URL: str = "https://data-api.binance.vision/api/v3/klines"
BINANCE_TICKER_URL: str = "https://data-api.binance.vision/api/v3/ticker/price"
KRAKEN_OHLC_URL: str = "https://api.kraken.com/0/public/OHLC"
KRAKEN_TICKER_URL: str = "https://api.kraken.com/0/public/Ticker"
DUKASCOPY_URL: str = "https://freeserv.dukascopy.com/2.0/"

# ── Model Storage ─────────────────────────────────────────────────────────────
MODEL_DIR: Path = Path(__file__).parents[3] / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR: Path = Path(__file__).parents[3] / "data_cache"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Forecasting defaults ──────────────────────────────────────────────────────
DEFAULT_CANDLES_LIMIT: int = 1000
DEFAULT_SYMBOL: str = "BTCUSDT"
DEFAULT_INTERVAL: str = "5m"
PRICE_FETCH_TIMEOUT: int = 10
PRICE_FETCH_RETRIES: int = 2

# ── Request headers ───────────────────────────────────────────────────────────
REQUEST_HEADERS: dict = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Supported crypto instruments ──────────────────────────────────────────────
CRYPTO_PAIRS: dict = {
    "BTCUSDT":  {"binance": "BTC/USDT",  "kraken": "XBTUSD",   "label": "BTC / USDT"},
    "ETHUSDT":  {"binance": "ETH/USDT",  "kraken": "ETHUSD",   "label": "ETH / USDT"},
    "BNBUSDT":  {"binance": "BNB/USDT",  "kraken": "BNBUSD",   "label": "BNB / USDT"},
    "SOLUSDT":  {"binance": "SOL/USDT",  "kraken": "SOLUSD",   "label": "SOL / USDT"},
    "ADAUSDT":  {"binance": "ADA/USDT",  "kraken": "ADAUSD",   "label": "ADA / USDT"},
    "XRPUSDT":  {"binance": "XRP/USDT",  "kraken": "XRPUSD",   "label": "XRP / USDT"},
    "DOGEUSDT": {"binance": "DOGE/USDT", "kraken": "XDGUSD",   "label": "DOGE / USDT"},
    "LINKUSDT": {"binance": "LINK/USDT", "kraken": "LINKUSD",  "label": "LINK / USDT"},
    "AVAXUSDT": {"binance": "AVAX/USDT", "kraken": "AVAXUSD",  "label": "AVAX / USDT"},
    "DOTUSDT":  {"binance": "DOT/USDT",  "kraken": "DOTUSD",   "label": "DOT / USDT"},
}

# ── Supported forex instruments ───────────────────────────────────────────────
FOREX_PAIRS: dict = {
    "XAUUSD": {"dukascopy": "XAUUSD", "label": "XAU / USD"},
    "USDCAD": {"dukascopy": "USDCAD", "label": "USD / CAD"},
    "USDCHF": {"dukascopy": "USDCHF", "label": "USD / CHF"},
    "EURUSD": {"dukascopy": "EURUSD", "label": "EUR / USD"},
}

# ── Valid timeframes per market ───────────────────────────────────────────────
CRYPTO_TIMEFRAMES: list = ["1m", "5m", "15m", "1h", "4h", "1d"]
FOREX_TIMEFRAMES: list = ["1m", "5m", "15m", "1h", "4h", "1d"]

# Binance interval aliases
BINANCE_INTERVAL_MAP: dict = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}

# Kraken interval aliases (in minutes)
KRAKEN_INTERVAL_MAP: dict = {
    "1m": "1", "5m": "5", "15m": "15",
    "1h": "60", "4h": "240", "1d": "1440",
}
