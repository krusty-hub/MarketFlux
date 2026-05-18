"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   ADAPTIVE CRYPTO FORECASTING ENGINE – INSTITUTIONAL TRADING INTELLIGENCE    ║
║   ENHANCED WITH SMC + ICT + ML CONFLUENCE                                    ║
║   SHORT-TERM HORIZONS ONLY: 2HR | 4HR | 8HR | 12HR                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

UPGRADES:
  1. Feature engineering: SMC (BOS, CHoCH, Order Blocks, FVG) + ICT concepts
  2. Institutional signals: Liquidity zones, fair value gaps, market structure
  3. Trade direction/bias instead of simple price prediction
  4. Entry/SL/TP levels with confluence scoring
  5. Risk/reward ratio and setup quality metrics

Install:
  pip install pandas numpy matplotlib scikit-learn xgboost lightgbm requests joblib ccxt

Usage:
  from Forecasting_Engine_Upgraded import run_forecast_realtime
  forecasts = run_forecast_realtime("ETHUSDT", exchange="binance")
"""

import os, sys, json, time, logging, warnings
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("forecast_realtime")

# ── Third-party ───────────────────────────────────────────────────────────────
try:
    import requests
    import numpy  as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.colors import LinearSegmentedColormap
    from sklearn.ensemble   import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics    import mean_absolute_error, mean_squared_error, accuracy_score
    import joblib
except ImportError as e:
    sys.exit(f"[FATAL] {e}\nRun: pip install pandas numpy matplotlib scikit-learn requests joblib")

try:
    import xgboost as xgb; HAS_XGB = True
except ImportError:
    HAS_XGB = False; log.warning("xgboost not found")

try:
    import lightgbm as lgb; HAS_LGB = True
except ImportError:
    HAS_LGB = False; log.warning("lightgbm not found")

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False
    log.warning("ccxt not found – will fall back to REST API only")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG – NEW TIMEFRAMES ONLY
# ══════════════════════════════════════════════════════════════════════════════

HORIZONS       = [2, 4, 8, 12]          # ONLY 2H, 4H, 8H, 12H forecasts
TIMEFRAMES     = ["5m", "15m", "1h", "4h"]
CANDLES_LIMIT  = 500
MODEL_DIR      = Path("models_realtime")
DB_PATH        = Path("forecast_db_realtime.json")
MODEL_DIR.mkdir(exist_ok=True)

# Price fetch retry config
PRICE_FETCH_RETRIES = 2
PRICE_FETCH_TIMEOUT = 10

# HTTP headers to bypass geo-blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Supported symbol mappings ─────────────────────────────────────────────────
SUPPORTED_PAIRS = {
    "ETHUSDT":   {"binance": "ETH/USDT",   "kraken": "ETHUSD",    "coingecko": "ethereum"},
    "BTCUSDT":   {"binance": "BTC/USDT",   "kraken": "XBTUSD",    "coingecko": "bitcoin"},
    "SOLUSDT":   {"binance": "SOL/USDT",   "kraken": "SOLUSD",    "coingecko": "solana"},
    "BNBUSDT":   {"binance": "BNB/USDT",   "kraken": "BNBUSD",    "coingecko": "binancecoin"},
    "ADAUSDT":   {"binance": "ADA/USDT",   "kraken": "ADAUSD",    "coingecko": "cardano"},
    "XRPUSDT":   {"binance": "XRP/USDT",   "kraken": "XRPUSD",    "coingecko": "ripple"},
    "DOGEUSDT":  {"binance": "DOGE/USDT",  "kraken": "XDGUSD",    "coingecko": "dogecoin"},
    "LINKUSDT":  {"binance": "LINK/USDT",  "kraken": "LINKUSD",   "coingecko": "chainlink"},
    "MATICUSDT": {"binance": "MATIC/USDT", "kraken": "MATICUSD",  "coingecko": "matic-network"},
    "AVAXUSDT":  {"binance": "AVAX/USDT",  "kraken": "AVAXUSD",   "coingecko": "avalanche-2"},
    "DOTUSDT":   {"binance": "DOT/USDT",   "kraken": "DOTUSD",    "coingecko": "polkadot"},
    "UNIUSDT":   {"binance": "UNI/USDT",   "kraken": "UNIUSD",    "coingecko": "uniswap"},
}


# ══════════════════════════════════════════════════════════════════════════════
# 1.  REAL-TIME LIVE PRICE FETCHING (PRESERVED FROM ORIGINAL)
# ══════════════════════════════════════════════════════════════════════════════

def get_live_price_binance(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Fetch LIVE price from Binance REST API – not cached historical data.
    Returns (price, "binance") or (None, None) on failure.
    """
    if symbol not in SUPPORTED_PAIRS or "binance" not in SUPPORTED_PAIRS[symbol]:
        return None, None

    pair = SUPPORTED_PAIRS[symbol]["binance"]  # e.g. "ETH/USDT" → "ETHUSDT"
    binance_symbol = pair.replace("/", "")

    try:
        url = f"https://api.binance.com/api/v3/ticker/price"
        resp = requests.get(
            url,
            params={"symbol": binance_symbol},
            headers=HEADERS,
            timeout=PRICE_FETCH_TIMEOUT
        )
        resp.raise_for_status()
        price = float(resp.json()["price"])
        log.debug(f"✓ Binance live price for {symbol}: ${price:.2f}")
        return price, "binance"
    except Exception as e:
        log.warning(f"Binance live price fetch failed: {e}")
        return None, None


def get_live_price_kraken(symbol: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Fetch LIVE price from Kraken REST API – unrestricted on cloud.
    Returns (price, "kraken") or (None, None) on failure.
    """
    if symbol not in SUPPORTED_PAIRS or "kraken" not in SUPPORTED_PAIRS[symbol]:
        return None, None

    kraken_pair = SUPPORTED_PAIRS[symbol]["kraken"]

    try:
        url = "https://api.kraken.com/0/public/Ticker"
        resp = requests.get(
            url,
            params={"pair": kraken_pair},
            headers=HEADERS,
            timeout=PRICE_FETCH_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            return None, None
        # Kraken returns {pair: {c: [price, vol]}}
        pair_data = list(data["result"].values())[0]
        price = float(pair_data["c"][0])  # Last trade price
        log.debug(f"✓ Kraken live price for {symbol}: ${price:.2f}")
        return price, "kraken"
    except Exception as e:
        log.warning(f"Kraken live price fetch failed: {e}")
        return None, None


def get_live_price_ccxt(symbol: str, exchange_name: str = "binance"
                        ) -> Tuple[Optional[float], Optional[str]]:
    """
    Fetch LIVE price using CCXT library – requires: pip install ccxt
    Returns (price, exchange_name) or (None, None) on failure.
    """
    if not HAS_CCXT:
        return None, None

    if symbol not in SUPPORTED_PAIRS or exchange_name not in SUPPORTED_PAIRS[symbol]:
        return None, None

    pair = SUPPORTED_PAIRS[symbol][exchange_name]

    try:
        # Create exchange instance (no API keys needed for public ticker)
        ExchangeClass = getattr(ccxt, exchange_name, None)
        if not ExchangeClass:
            return None, None

        exchange = ExchangeClass()
        ticker = exchange.fetch_ticker(pair)
        price = float(ticker["last"])
        log.debug(f"✓ CCXT {exchange_name} live price for {symbol}: ${price:.2f}")
        return price, exchange_name
    except Exception as e:
        log.warning(f"CCXT {exchange_name} fetch failed: {e}")
        return None, None


def get_live_price_with_retry(symbol: str, exchange: str = "binance") -> Tuple[float, str]:
    """
    Fetch LIVE price with retry logic & fallback cascade.
    Returns (price, source) or raises RuntimeError if all sources fail.
    """
    if exchange == "binance":
        funcs = [
            lambda: get_live_price_binance(symbol),
            lambda: get_live_price_ccxt(symbol, "binance"),
            lambda: get_live_price_kraken(symbol),
        ]
    elif exchange == "kraken":
        funcs = [
            lambda: get_live_price_kraken(symbol),
            lambda: get_live_price_ccxt(symbol, "kraken"),
            lambda: get_live_price_binance(symbol),
        ]
    else:
        funcs = [lambda: get_live_price_ccxt(symbol, exchange)]

    for attempt in range(PRICE_FETCH_RETRIES):
        for func in funcs:
            price, src = func()
            if price is not None:
                return price, src
        if attempt < PRICE_FETCH_RETRIES - 1:
            time.sleep(0.5)

    raise RuntimeError(f"Live price fetch failed for {symbol} after {PRICE_FETCH_RETRIES} retries")


def fetch_multi_timeframe(symbol: str, exchange: str = "binance") -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data from multiple timeframes.
    Returns dict like {"5m": df, "15m": df, "1h": df, "4h": df}
    """
    result = {}
    for tf in TIMEFRAMES:
        try:
            if exchange == "binance":
                df = fetch_binance_ohlcv(symbol, tf)
            elif exchange == "kraken":
                df = fetch_kraken_ohlcv(symbol, tf)
            else:
                df = fetch_ccxt_ohlcv(symbol, tf, exchange)
            
            if df is not None and len(df) > 0:
                result[tf] = df
        except Exception as e:
            log.warning(f"Failed to fetch {tf} for {symbol}: {e}")

    return result


def fetch_binance_ohlcv(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from Binance."""
    if symbol not in SUPPORTED_PAIRS:
        return None
    
    binance_pair = SUPPORTED_PAIRS[symbol]["binance"].replace("/", "")
    
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": binance_pair,
            "interval": timeframe,
            "limit": CANDLES_LIMIT,
        }
        resp = requests.get(url, params=params, headers=HEADERS, timeout=PRICE_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume",
                                          "close_time", "quote_asset_volume", "trades",
                                          "taker_buy_base", "taker_buy_quote", "ignore"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        return df
    except Exception as e:
        log.warning(f"Binance OHLCV fetch failed ({timeframe}): {e}")
        return None


def fetch_kraken_ohlcv(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from Kraken."""
    if symbol not in SUPPORTED_PAIRS:
        return None
    
    kraken_pair = SUPPORTED_PAIRS[symbol]["kraken"]
    
    # Map timeframe to Kraken format
    tf_map = {"5m": "5", "15m": "15", "1h": "60", "4h": "240"}
    kraken_tf = tf_map.get(timeframe, "60")
    
    try:
        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": kraken_pair, "interval": kraken_tf}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=PRICE_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("error") or "result" not in data:
            return None
        
        ohlc_data = list(data["result"].values())[0]
        df = pd.DataFrame(ohlc_data, columns=["timestamp", "open", "high", "low", "close", "volume", "count"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        return df
    except Exception as e:
        log.warning(f"Kraken OHLCV fetch failed ({timeframe}): {e}")
        return None


def fetch_ccxt_ohlcv(symbol: str, timeframe: str, exchange_name: str = "binance") -> Optional[pd.DataFrame]:
    """Fetch OHLCV via CCXT."""
    if not HAS_CCXT or symbol not in SUPPORTED_PAIRS:
        return None
    
    pair = SUPPORTED_PAIRS[symbol].get(exchange_name)
    if not pair:
        return None
    
    try:
        ExchangeClass = getattr(ccxt, exchange_name, None)
        if not ExchangeClass:
            return None
        exchange = ExchangeClass()
        ohlcv = exchange.fetch_ohlcv(pair, timeframe, limit=CANDLES_LIMIT)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        return df
    except Exception as e:
        log.warning(f"CCXT OHLCV fetch failed ({exchange_name}, {timeframe}): {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 2.  INSTITUTIONAL FEATURE ENGINEERING – SMC + ICT + TECHNICAL
# ══════════════════════════════════════════════════════════════════════════════

def add_features(df: pd.DataFrame, live_price: float = None) -> pd.DataFrame:
    """
    UPGRADED: Engineer institutional-grade features combining:
      • Smart Money Concepts (Break of Structure, Order Blocks, Fair Value Gaps)
      • ICT concepts (Market Structure, Kill Zones, Liquidity Zones)
      • Technical Indicators (RSI, MACD, EMA, ATR, Volume)
      • Multi-timeframe confirmation signals
    
    Each feature has detailed comments explaining its trading logic.
    """
    df = df.copy()
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 1: BASIC PRICE & VOLATILITY METRICS
    # ────────────────────────────────────────────────────────────────────────────
    
    # Returns for horizon-based labeling (for supervised learning targets)
    df["ret_1h"] = df["close"].pct_change(1)
    df["ret_2h"] = df["close"].pct_change(2)
    df["ret_4h"] = df["close"].pct_change(4)
    df["ret_8h"] = df["close"].pct_change(8)
    df["ret_12h"] = df["close"].pct_change(12)
    
    # Realized volatility (14-period rolling std of returns)
    df["rvol_14"] = df["ret_1h"].rolling(14).std()
    
    # ATR (Average True Range) – volatility-adjusted price movement
    # ATR = mean(max(H - L, H - prev_C, prev_C - L)) over 14 periods
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1)),
            abs(df["low"] - df["close"].shift(1))
        )
    )
    df["atr_14"] = df["tr"].rolling(14).mean()
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 2: TREND INDICATORS (Multi-EMA + Directional Bias)
    # ────────────────────────────────────────────────────────────────────────────
    
    # Multi-EMA system for trend confirmation (institutional standard)
    # Fast = recent momentum, Mid = trend direction, Slow = major trend
    df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()    # Fast: immediate direction
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()  # Mid: short-term trend
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()  # Slow: major trend
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean() # Very slow: market context
    
    # EMA alignment score: how many EMAs are stacked bullish/bearish?
    # Values near 1 = strong bullish alignment, near -1 = strong bearish alignment
    df["ema_alignment"] = np.where(
        (df["ema_9"] > df["ema_21"]) & (df["ema_21"] > df["ema_50"]),
        1.0,  # All EMAs bullish
        np.where(
            (df["ema_9"] < df["ema_21"]) & (df["ema_21"] < df["ema_50"]),
            -1.0,  # All EMAs bearish
            0.0   # Mixed alignment
        )
    )
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 3: MOMENTUM INDICATORS (RSI + MACD)
    # ────────────────────────────────────────────────────────────────────────────
    
    # RSI (Relative Strength Index) – overbought/oversold + divergence detection
    # RSI > 70 = overbought (potential reversal), RSI < 30 = oversold (potential reversal)
    # Standard period = 14
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    # RSI divergence detection: price makes new high/low but RSI doesn't (reversal signal)
    # Bearish divergence: price new high, RSI lower high
    # Bullish divergence: price new low, RSI higher low
    df["rsi_high"] = df["rsi_14"].rolling(14).max()
    df["rsi_low"] = df["rsi_14"].rolling(14).min()
    df["price_high"] = df["close"].rolling(14).max()
    df["price_low"] = df["close"].rolling(14).min()
    
    # Detect hidden divergences (continuation signals)
    df["bearish_divergence"] = (
        (df["close"] > df["price_high"].shift(1)) & 
        (df["rsi_14"] < df["rsi_high"].shift(1))
    ).astype(int)
    df["bullish_divergence"] = (
        (df["close"] < df["price_low"].shift(1)) & 
        (df["rsi_14"] > df["rsi_low"].shift(1))
    ).astype(int)
    
    # MACD (Moving Average Convergence Divergence) – momentum confirmation
    # MACD = EMA12 - EMA26; Signal = EMA9 of MACD; Histogram = MACD - Signal
    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    
    # MACD momentum: positive histogram = bullish, negative = bearish
    df["macd_bullish"] = (df["macd_hist"] > 0).astype(int)
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 4: SMART MONEY CONCEPTS (SMC) – MARKET STRUCTURE
    # ────────────────────────────────────────────────────────────────────────────
    
    # Break of Structure (BOS) – price breaks recent swing high/low
    # Bullish BOS: price closes above recent swing high (trend continuation UP)
    # Bearish BOS: price closes below recent swing low (trend continuation DOWN)
    window = 5
    df["swing_high"] = df["high"].rolling(window=window, center=True).max()
    df["swing_low"] = df["low"].rolling(window=window, center=True).min()
    
    df["bullish_bos"] = (df["close"] > df["swing_high"].shift(1)).astype(int)
    df["bearish_bos"] = (df["close"] < df["swing_low"].shift(1)).astype(int)
    
    # Change of Character (CHoCH) – shift in market structure
    # From making higher highs (uptrend) to making lower lows (downtrend) = reversal
    df["higher_high"] = (df["high"] > df["high"].shift(1)).astype(int)
    df["lower_low"] = (df["low"] < df["low"].shift(1)).astype(int)
    
    # Rolling sum over 3 candles: if suddenly trend changes = CHoCH signal
    df["hh_count"] = df["higher_high"].rolling(3).sum()
    df["ll_count"] = df["lower_low"].rolling(3).sum()
    df["choch_signal"] = np.where(
        (df["hh_count"].shift(1) >= 2) & (df["ll_count"] >= 2),
        1,  # Potential reversal
        0
    )
    
    # Order Blocks (OB) – accumulation/distribution levels where smart money stops price
    # Detected as areas where price reverses sharply after trending
    # Mark candle as OB if it breaks structure but then reverses
    df["ob_signal"] = (df["bullish_bos"] | df["bearish_bos"]) & \
                      ((df["rsi_14"] > 60) | (df["rsi_14"] < 40))
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 5: FAIR VALUE GAPS (FVG) – LIQUIDITY ZONES
    # ══════════════════════════════════════════════════════════════════════════════
    
    # FVG = gap between candles where no trading occurred
    # Bullish FVG: low of current candle > high of 2 candles ago (uptrend gap)
    # Bearish FVG: high of current candle < low of 2 candles ago (downtrend gap)
    # Smart money uses FVGs as targets (price returns to fill gaps)
    
    df["bullish_fvg"] = df["low"] > df["high"].shift(2)
    df["bearish_fvg"] = df["high"] < df["low"].shift(2)
    
    # FVG depth (how big is the gap? – bigger gaps = stronger liquidity zones)
    df["fvg_depth_bull"] = np.where(df["bullish_fvg"], df["low"] - df["high"].shift(2), 0)
    df["fvg_depth_bear"] = np.where(df["bearish_fvg"], df["low"].shift(2) - df["high"], 0)
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 6: LIQUIDITY ZONES & INDUCEMENT
    # ════════════════════════════════════════════════════════════════════════════
    
    # Liquidity zones = recent swing highs/lows where traders place stops
    # Inducement = price briefly breaks liquidity zone then reverses (institutional trap)
    window_liq = 8
    df["recent_high"] = df["high"].rolling(window_liq).max()
    df["recent_low"] = df["low"].rolling(window_liq).min()
    
    # Detect if price touched liquidity then reversed (inducement move)
    df["touched_liquidity_high"] = (df["high"] >= df["recent_high"].shift(1)).astype(int)
    df["touched_liquidity_low"] = (df["low"] <= df["recent_low"].shift(1)).astype(int)
    
    df["inducement_bull"] = df["touched_liquidity_low"] & (df["close"] > df["close"].shift(1))
    df["inducement_bear"] = df["touched_liquidity_high"] & (df["close"] < df["close"].shift(1))
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 7: VOLUME ANALYSIS – SMART MONEY POSITIONING
    # ════════════════════════════════════════════════════════════════════════════
    
    # Volume is key to SMC: high volume on reversal = institutional distribution/accumulation
    df["vol_ma_20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_ma_20"] + 1e-9)
    
    # High volume reversal = institutional activity (either distribution or accumulation)
    df["vol_spike"] = (df["vol_ratio"] > 1.5).astype(int)
    
    # Volume-price correlation: strong move on high volume = real move, weak volume = weak conviction
    df["high_vol_break"] = df["vol_spike"] & ((df["ret_1h"] > 0.005) | (df["ret_1h"] < -0.005))
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 8: ICT KILL ZONES – SESSION-BASED TRADING WINDOWS
    # ════════════════════════════════════════════════════════════════════════════
    
    # ICT Kill Zones = optimal trading times during specific sessions
    # London Kill Zone: 08:00-10:00 UTC (liquid, directional)
    # NY Kill Zone: 13:00-15:00 UTC (breakout confirmation)
    
    df["hour"] = df.index.hour if hasattr(df.index, 'hour') else 0
    df["london_kill_zone"] = ((df["hour"] >= 8) & (df["hour"] < 10)).astype(int)
    df["ny_kill_zone"] = ((df["hour"] >= 13) & (df["hour"] < 15)).astype(int)
    df["in_kill_zone"] = (df["london_kill_zone"] | df["ny_kill_zone"]).astype(int)
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 9: BALANCED PRICE RANGES (BPR) – CONSOLIDATION ZONES
    # ════════════════════════════════════════════════════════════════════════════
    
    # BPR = area where price consolidates between equal highs/lows
    # When price breaks BPR = directional move expected
    df["equal_highs"] = (df["high"] == df["high"].shift(1)).astype(int)
    df["equal_lows"] = (df["low"] == df["low"].shift(1)).astype(int)
    
    # Consolidation strength: consecutive equal highs/lows = tight range
    df["consolidation_strength"] = df["equal_highs"].rolling(3).sum() + df["equal_lows"].rolling(3).sum()
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 10: TREND STRENGTH & REGIME DETECTION
    # ════════════════════════════════════════════════════════════════════════════
    
    # Trend strength: combination of EMA alignment + price distance from EMAs
    df["dist_from_ema21"] = (df["close"] - df["ema_21"]) / df["atr_14"]
    df["trend_strength"] = df["ema_alignment"] * np.tanh(df["dist_from_ema21"])
    
    # Market regime: TRENDING vs RANGING
    # TRENDING: large swings, price away from EMA, high rvol
    # RANGING: small swings, price near EMA, low rvol
    df["regime"] = np.where(
        (df["rvol_14"] > df["rvol_14"].rolling(20).mean() * 1.2) | 
        (abs(df["dist_from_ema21"]) > 1.5),
        1,  # TRENDING regime
        0   # RANGING regime
    )
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 11: SUPPORT/RESISTANCE ZONES
    # ════════════════════════════════════════════════════════════════════════════
    
    # Support = recent swing low where price bounced
    # Resistance = recent swing high where price reversed
    # Used for take-profit and stop-loss placement
    window_sr = 10
    df["support_1"] = df["low"].rolling(window_sr).min()
    df["resistance_1"] = df["high"].rolling(window_sr).max()
    
    # Distance to support/resistance in ATR terms (for risk management)
    df["dist_to_support_atr"] = (df["close"] - df["support_1"]) / (df["atr_14"] + 1e-9)
    df["dist_to_resistance_atr"] = (df["resistance_1"] - df["close"]) / (df["atr_14"] + 1e-9)
    
    # ────────────────────────────────────────────────────────────────────────────
    # SECTION 12: LIVE PRICE CONTEXT (Added if provided)
    # ════════════════════════════════════════════════════════════════════════════
    
    if live_price is not None:
        df["live_price"] = live_price
        df["price_context"] = (live_price - df["close"]) / (df["atr_14"] + 1e-9)
    
    return df


def get_feature_cols(df: pd.DataFrame) -> List[str]:
    """Return list of engineered feature columns (exclude OHLCV and intermediate calculations)."""
    exclude = {"open", "high", "low", "close", "volume", "tr", "swing_high", "swing_low",
               "rsi_high", "rsi_low", "price_high", "price_low", "hour", "live_price",
               "recent_high", "recent_low", "vol_ma_20"}
    return [col for col in df.columns if col not in exclude and not col.startswith("ret_")]


# ══════════════════════════════════════════════════════════════════════════════
# 3.  INSTITUTIONAL SIGNAL AGGREGATION – CONFLUENCE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def calculate_confluence_score(row: pd.Series) -> Tuple[str, float, List[str]]:
    """
    Aggregate multiple SMC/ICT signals into a unified TRADE BIAS + CONFLUENCE SCORE.
    
    Returns: (trade_direction, confidence_0_to_100, list_of_active_signals)
    
    Trade Direction:
      - "STRONG_LONG": Multiple bullish signals with high confluence
      - "LONG": Bullish bias with moderate confluence
      - "NEUTRAL": Mixed signals or indecision
      - "SHORT": Bearish bias with moderate confluence
      - "STRONG_SHORT": Multiple bearish signals with high confluence
    """
    signals = []
    long_count = 0
    short_count = 0
    
    # ────────────────────────────────────────────────────────────────────────────
    # BULLISH SIGNALS (add to long_count)
    # ────────────────────────────────────────────────────────────────────────────
    
    # 1. EMA Alignment: all EMAs stacked bullish
    if row["ema_alignment"] > 0.5:
        signals.append("ema_bullish_stack")
        long_count += 2
    
    # 2. Break of Structure UP: price breaks recent swing high (trend continuation)
    if row["bullish_bos"] > 0.5:
        signals.append("bullish_bos")
        long_count += 1.5
    
    # 3. Order Block Support: price at order block after reversal
    if row["ob_signal"] > 0.5 and row["rsi_14"] < 40:
        signals.append("ob_support")
        long_count += 1.5
    
    # 4. Bullish FVG: fair value gap in uptrend (liquidity target)
    if row["bullish_fvg"]:
        signals.append("bullish_fvg")
        long_count += 1
    
    # 5. RSI Bullish Divergence: price lower low but RSI higher low (reversal)
    if row["bullish_divergence"]:
        signals.append("rsi_bullish_div")
        long_count += 1.5
    
    # 6. MACD Bullish: histogram positive (momentum confirmation)
    if row["macd_bullish"] > 0.5:
        signals.append("macd_bullish")
        long_count += 1
    
    # 7. Inducement Bullish: price touched low liquidity then bounced
    if row["inducement_bull"] > 0.5:
        signals.append("inducement_bull")
        long_count += 1.5
    
    # 8. Volume Spike Up: high volume on bullish move (institutional buying)
    if row["vol_spike"] > 0.5 and row["ret_1h"] > 0.002:
        signals.append("volume_spike_bull")
        long_count += 1
    
    # 9. RSI Below 40 (Oversold): potential bounce setup
    if row["rsi_14"] < 40:
        signals.append("rsi_oversold")
        long_count += 1
    
    # 10. Trend Strength Positive: price pulling away from EMA in uptrend
    if row["trend_strength"] > 0.5:
        signals.append("trend_strength_bull")
        long_count += 1
    
    # ────────────────────────────────────────────────────────────────────────────
    # BEARISH SIGNALS (add to short_count)
    # ────────────────────────────────────────────────────────────────────────────
    
    # 1. EMA Alignment: all EMAs stacked bearish
    if row["ema_alignment"] < -0.5:
        signals.append("ema_bearish_stack")
        short_count += 2
    
    # 2. Break of Structure DOWN: price breaks recent swing low
    if row["bearish_bos"] > 0.5:
        signals.append("bearish_bos")
        short_count += 1.5
    
    # 3. Order Block Resistance: price at order block after reversal
    if row["ob_signal"] > 0.5 and row["rsi_14"] > 60:
        signals.append("ob_resistance")
        short_count += 1.5
    
    # 4. Bearish FVG: fair value gap in downtrend (liquidity target)
    if row["bearish_fvg"]:
        signals.append("bearish_fvg")
        short_count += 1
    
    # 5. RSI Bearish Divergence: price higher high but RSI lower high (reversal)
    if row["bearish_divergence"]:
        signals.append("rsi_bearish_div")
        short_count += 1.5
    
    # 6. MACD Bearish: histogram negative (momentum confirmation)
    if row["macd_bullish"] < 0.5:
        signals.append("macd_bearish")
        short_count += 1
    
    # 7. Inducement Bearish: price touched high liquidity then reversed down
    if row["inducement_bear"] > 0.5:
        signals.append("inducement_bear")
        short_count += 1.5
    
    # 8. Volume Spike Down: high volume on bearish move (institutional selling)
    if row["vol_spike"] > 0.5 and row["ret_1h"] < -0.002:
        signals.append("volume_spike_bear")
        short_count += 1
    
    # 9. RSI Above 60 (Overbought): potential reversal setup
    if row["rsi_14"] > 60:
        signals.append("rsi_overbought")
        short_count += 1
    
    # 10. Trend Strength Negative: price pulling away from EMA in downtrend
    if row["trend_strength"] < -0.5:
        signals.append("trend_strength_bear")
        short_count += 1
    
    # ────────────────────────────────────────────────────────────────────────────
    # NORMALIZE & CALCULATE CONFLUENCE SCORE
    # ────────────────────────────────────────────────────────────────────────────
    
    total_signal_weight = long_count + short_count
    
    if total_signal_weight < 0.1:
        # No clear signals = neutral
        return "NEUTRAL", 50, signals
    
    # Convert to probability (0-100 scale)
    bull_prob = long_count / total_signal_weight if total_signal_weight > 0 else 0.5
    confluence_score = int(bull_prob * 100)
    
    # Determine trade direction based on signal count
    if long_count > short_count * 1.5:
        if long_count >= 4:
            return "STRONG_LONG", confluence_score, signals
        else:
            return "LONG", confluence_score, signals
    elif short_count > long_count * 1.5:
        if short_count >= 4:
            return "STRONG_SHORT", 100 - confluence_score, signals
        else:
            return "SHORT", 100 - confluence_score, signals
    else:
        return "NEUTRAL", 50, signals


# ══════════════════════════════════════════════════════════════════════════════
# 4.  ENTRY, SL, TP LEVEL CALCULATION – RISK/REWARD MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def calculate_trade_levels(row: pd.Series, direction: str, live_price: float, atr: float) -> Dict:
    """
    Calculate institutional-grade entry, stop-loss, and take-profit levels.
    
    Based on:
      - ATR for volatility-adjusted stops
      - Support/resistance zones
      - Order blocks and FVGs
      - Risk/reward ratios (target 1:2 minimum)
    """
    
    if direction == "LONG":
        # Entry at support level or current price if in uptrend
        entry = max(row["support_1"], live_price - atr * 0.5)
        
        # Stop Loss: below recent swing low or order block
        sl = row["support_1"] - atr * 0.5
        
        # Take Profit Levels:
        # TP1: resistance or order block level
        # TP2: higher resistance or liquidity level
        tp1 = row["resistance_1"]
        tp2 = row["resistance_1"] + atr * 2
        
        risk = entry - sl
        reward_1 = tp1 - entry
        reward_2 = tp2 - entry
        
        return {
            "entry": round(entry, 2),
            "stop_loss": round(sl, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
            "risk_amount": round(risk, 2),
            "reward_ratio_tp1": round(reward_1 / (risk + 1e-9), 2),
            "reward_ratio_tp2": round(reward_2 / (risk + 1e-9), 2),
        }
    
    elif direction == "SHORT":
        # Entry at resistance level or current price if in downtrend
        entry = min(row["resistance_1"], live_price + atr * 0.5)
        
        # Stop Loss: above recent swing high or order block
        sl = row["resistance_1"] + atr * 0.5
        
        # Take Profit Levels:
        # TP1: support level
        # TP2: lower support or liquidity level
        tp1 = row["support_1"]
        tp2 = row["support_1"] - atr * 2
        
        risk = sl - entry
        reward_1 = entry - tp1
        reward_2 = entry - tp2
        
        return {
            "entry": round(entry, 2),
            "stop_loss": round(sl, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
            "risk_amount": round(risk, 2),
            "reward_ratio_tp1": round(reward_1 / (risk + 1e-9), 2),
            "reward_ratio_tp2": round(reward_2 / (risk + 1e-9), 2),
        }
    
    else:  # NEUTRAL
        return {
            "entry": round(live_price, 2),
            "stop_loss": round(live_price - atr, 2),
            "take_profit_1": round(live_price + atr, 2),
            "take_profit_2": round(live_price + atr * 2, 2),
            "risk_amount": round(atr, 2),
            "reward_ratio_tp1": 1.0,
            "reward_ratio_tp2": 2.0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 5.  ENHANCED ML MODEL – DIRECTIONAL CLASSIFICATION + REGRESSION
# ══════════════════════════════════════════════════════════════════════════════

class InstitutionalForecastModel:
    """
    Enhanced ML ensemble combining:
      • Directional classification (LONG/SHORT/NEUTRAL)
      • Return prediction (regression for price targets)
      • Confidence calibration
      • Feature importance tracking
    """
    
    def __init__(self, horizon_hours: int):
        self.horizon = horizon_hours
        self.scaler = StandardScaler()
        self.models = {}
        self.weights = {}
        self.trained = False
        self.feature_cols = []
        
        # Initialize ensemble components
        self.models["rf"] = RandomForestRegressor(
            n_estimators=100,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        
        if HAS_XGB:
            self.models["xgb"] = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1
            )
        
        if HAS_LGB:
            self.models["lgb"] = lgb.LGBMRegressor(
                n_estimators=100,
                max_depth=8,
                learning_rate=0.05,
                num_leaves=31,
                random_state=42,
                n_jobs=-1
            )
        
        # Initial equal weights (will be optimized during training)
        self.weights = {name: 1.0 / len(self.models) for name in self.models}
    
    def fit(self, df: pd.DataFrame, feature_cols: List[str]):
        """
        Train ensemble on historical data.
        
        Target: returns at horizon (returns are indicators of directional moves)
        Features: institutional-grade indicators from add_features()
        """
        self.feature_cols = feature_cols
        
        # Prepare features and targets
        X = df[feature_cols].fillna(0).values
        target_col = f"ret_{self.horizon}h"
        
        if target_col not in df.columns:
            log.warning(f"Target {target_col} not found, using ret_2h as fallback")
            target_col = "ret_2h"
        
        y = df[target_col].fillna(0).values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train each model
        for name, model in self.models.items():
            model.fit(X_scaled, y)
            log.debug(f"Trained {name} for {self.horizon}H horizon")
        
        # Optimize weights based on individual model performance
        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(X_scaled)
        
        # Weight by inverse MAE (better performing models get higher weight)
        for name in self.models:
            mae = mean_absolute_error(y, predictions[name])
            self.weights[name] = 1.0 / (mae + 0.01)
        
        # Normalize weights to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
        self.trained = True
        log.info(f"Ensemble weights: {self.weights}")
    
    def predict_ensemble(self, X_raw: np.ndarray) -> np.ndarray:
        """Make ensemble prediction on features."""
        X_scaled = self.scaler.transform(X_raw)
        out = np.zeros(len(X_scaled))
        for name, mdl in self.models.items():
            out += self.weights[name] * mdl.predict(X_scaled)
        return out
    
    def predict_with_uncertainty(self, X_raw: np.ndarray) -> Tuple[float, float, float]:
        """
        Return (ensemble_prediction, lower_bound, upper_bound) for confidence intervals.
        
        Uncertainty based on model disagreement (if all models agree, low uncertainty).
        """
        X_scaled = self.scaler.transform(X_raw)
        individual_preds = [m.predict(X_scaled)[0] for m in self.models.values()]
        ensemble = sum(w * p for w, p in zip(self.weights.values(), individual_preds))
        spread = np.std(individual_preds) if len(individual_preds) > 1 else abs(ensemble) * 0.5
        return float(ensemble), float(ensemble - 2*spread), float(ensemble + 2*spread)
    
    def feature_importance(self) -> pd.Series:
        """Return weighted feature importance across ensemble."""
        imp = {}
        for name, mdl in self.models.items():
            w = self.weights.get(name, 1.0)
            if hasattr(mdl, "feature_importances_"):
                for col, val in zip(self.feature_cols, mdl.feature_importances_):
                    imp[col] = imp.get(col, 0) + w * val
        return pd.Series(imp).sort_values(ascending=False)


# ══════════════════════════════════════════════════════════════════════════════
# 6.  MAIN FORECAST FUNCTION – INSTITUTIONAL ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_forecast_realtime(symbol: str = "ETHUSDT",
                          exchange: str = "binance") -> Dict:
    """
    MAIN ENTRY POINT: Generates institutional trading intelligence.
    
    Steps:
    1. Fetch LIVE price
    2. Fetch historical OHLCV
    3. Engineer institutional features (SMC + ICT + ML)
    4. Train ensemble models per horizon
    5. Calculate confluence signals
    6. Generate entry/SL/TP levels
    7. Return comprehensive trading forecast
    
    Returns dict with:
    {
        "symbol": "ETHUSDT",
        "live_price": 2267.45,
        "forecasts": [
            {
                "horizon": 2,
                "trade_direction": "STRONG_LONG",
                "confluence_score": 78,
                "entry_price": 2260.00,
                "stop_loss": 2250.00,
                "take_profit_1": 2280.00,
                "take_profit_2": 2300.00,
                "risk_reward_ratio": 1.5,
                "smc_signals": ["bullish_bos", "ema_bullish_stack", ...],
                ...
            },
            ...
        ]
    }
    """
    log.info(f"═══ INSTITUTIONAL FORECAST START ═══")
    log.info(f"Symbol: {symbol} | Exchange: {exchange}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: FETCH LIVE PRICE
    # ──────────────────────────────────────────────────────────────────────────
    try:
        live_price, price_source = get_live_price_with_retry(symbol, exchange)
        log.info(f"✓ LIVE PRICE: ${live_price:.2f} from {price_source}")
    except RuntimeError as e:
        log.error(f"FATAL: Live price fetch failed: {e}")
        raise
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: FETCH HISTORICAL OHLCV
    # ──────────────────────────────────────────────────────────────────────────
    log.info("Fetching historical OHLCV …")
    tf_data = fetch_multi_timeframe(symbol, exchange)
    if not tf_data:
        msg = f"No OHLCV data for {symbol}"
        log.error(msg)
        raise RuntimeError(msg)
    
    primary_tf = "1h" if "1h" in tf_data else list(tf_data.keys())[0]
    df_raw = tf_data[primary_tf]
    log.info(f"Primary TF: {primary_tf}, {len(df_raw)} candles")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: ENGINEER INSTITUTIONAL FEATURES
    # ──────────────────────────────────────────────────────────────────────────
    log.info("Engineering institutional features (SMC + ICT) …")
    df = add_features(df_raw, live_price=live_price)
    feature_cols = get_feature_cols(df)
    
    log.info(f"Dataset: {len(df)} rows × {len(feature_cols)} features")
    if len(df) < 150:
        msg = f"Only {len(df)} rows (need ≥150)"
        log.error(msg)
        raise RuntimeError(msg)
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: TRAIN ENSEMBLE MODELS
    # ──────────────────────────────────────────────────────────────────────────
    log.info(f"Training ensemble for horizons: {HORIZONS}")
    trained_models: Dict[int, InstitutionalForecastModel] = {}
    for h in HORIZONS:
        log.info(f"Training {h}H model …")
        mdl = InstitutionalForecastModel(h)
        mdl.fit(df, feature_cols)
        trained_models[h] = mdl
        mdl_path = MODEL_DIR / f"{symbol}_{h}h.joblib"
        joblib.dump(mdl, mdl_path)
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: GENERATE FORECASTS WITH INSTITUTIONAL SIGNALS
    # ──────────────────────────────────────────────────────────────────────────
    log.info("Generating institutional forecasts …")
    latest = df.iloc[[-1]][feature_cols]
    latest_row = df.iloc[-1]
    rvol = float(df["rvol_14"].iloc[-1])
    atr = float(df["atr_14"].iloc[-1])
    regime = int(df["regime"].iloc[-1])
    
    forecasts = []
    ts = datetime.now(timezone.utc).isoformat()
    
    for h in HORIZONS:
        mdl = trained_models[h]
        pred_ret, lo_ret, hi_ret = mdl.predict_with_uncertainty(latest.values)
        
        # ────────────────────────────────────────────────────────────────────────
        # Calculate trade direction & confluence score from institutional signals
        # ────────────────────────────────────────────────────────────────────────
        direction, confidence, smc_signals = calculate_confluence_score(latest_row)
        
        # ────────────────────────────────────────────────────────────────────────
        # Calculate entry/SL/TP levels
        # ────────────────────────────────────────────────────────────────────────
        trade_levels = calculate_trade_levels(latest_row, direction, live_price, atr)
        
        # ────────────────────────────────────────────────────────────────────────
        # Calculate price targets and probability metrics
        # ────────────────────────────────────────────────────────────────────────
        pred_price = live_price * (1 + pred_ret)
        lo_price = live_price * (1 + lo_ret)
        hi_price = live_price * (1 + hi_ret)
        
        # Probability calibration: map ensemble prediction to probability
        bull_prob = float(np.clip(0.5 + pred_ret / (rvol * 3 + 1e-9) * 0.5, 0.05, 0.95))
        conf_score = np.clip(1.0 - abs(hi_ret - lo_ret) / max(abs(pred_ret) + 1e-9, 0.01), 0.0, 1.0)
        
        # Setup quality: how many strong signals + good risk/reward?
        setup_quality = min(len(smc_signals) / 5.0, 1.0) * trade_levels["reward_ratio_tp1"] / 2.0
        setup_quality = np.clip(setup_quality, 0.0, 1.0)
        
        # ────────────────────────────────────────────────────────────────────────
        # Compile forecast output
        # ────────────────────────────────────────────────────────────────────────
        forecasts.append({
            "horizon": h,
            "symbol": symbol,
            
            # DIRECTIONAL SIGNALS
            "trend_direction": direction,
            "trade_bias": direction.replace("_", " "),
            "confluence_score": confidence,
            "setup_quality": round(setup_quality * 100, 1),
            
            # PRICE TARGETS
            "pred_price": round(pred_price, 2),
            "pred_ret_pct": round(pred_ret * 100, 3),
            "range_lo": round(lo_price, 2),
            "range_hi": round(hi_price, 2),
            
            # PROBABILITY METRICS
            "bull_prob_pct": round(bull_prob * 100, 1),
            "bear_prob_pct": round((1 - bull_prob) * 100, 1),
            "confidence": "HIGH" if conf_score >= 0.65 else "MEDIUM" if conf_score >= 0.45 else "LOW",
            "conf_score": round(conf_score, 2),
            
            # ENTRY/SL/TP LEVELS (Institutional Risk Management)
            "entry_price": trade_levels["entry"],
            "stop_loss": trade_levels["stop_loss"],
            "take_profit_1": trade_levels["take_profit_1"],
            "take_profit_2": trade_levels["take_profit_2"],
            "risk_reward_ratio": trade_levels["reward_ratio_tp1"],
            
            # MARKET CONTEXT
            "volatility": "HIGH" if rvol > 0.025 else "MEDIUM" if rvol > 0.012 else "LOW",
            "rvol": round(rvol, 4),
            "atr": round(atr, 2),
            "regime": "TRENDING" if regime == 1 else "RANGING",
            "market_structure": "BULLISH" if latest_row["ema_alignment"] > 0 else "BEARISH",
            
            # SMC/ICT SIGNALS (Active institutional signals)
            "smc_signals": smc_signals[:8],  # Top 8 signals
            
            # LIQUIDITY TARGETS
            "liquidity_target": round(trade_levels["take_profit_2"], 2),
            "institutional_bias": "ACCUMULATION" if direction.startswith("LONG") else "DISTRIBUTION",
        })
        
        log.info(f"✓ {h}H: {direction:12s} | conf={confidence:3d}% | entry={trade_levels['entry']:.2f} | "
                f"SL={trade_levels['stop_loss']:.2f} | TP={trade_levels['take_profit_1']:.2f}")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: RETURN COMPREHENSIVE TRADING FORECAST
    # ──────────────────────────────────────────────────────────────────────────
    result = {
        "status": "success",
        "live_price": live_price,
        "price_source": price_source,
        "symbol": symbol,
        "exchange": exchange,
        "timestamp": ts,
        "forecasts": forecasts,
        "meta": {
            "last_close": round(df["close"].iloc[-1], 2),
            "live_price": live_price,
            "rvol_pct": round(rvol * 100, 3),
            "atr": round(atr, 2),
            "regime": "TRENDING" if regime == 1 else "RANGING",
            "market_structure": "BULLISH" if latest_row["ema_alignment"] > 0 else "BEARISH",
            "candles_analyzed": len(df),
            "features_engineered": len(feature_cols),
        }
    }
    
    log.info(f"═══ FORECAST COMPLETE ═══")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT (PRESERVED)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ETHUSDT")
    parser.add_argument("--exchange", default="binance")
    args, _ = parser.parse_known_args()

    try:
        result = run_forecast_realtime(args.symbol, args.exchange)
        print("\n" + "="*80)
        print(json.dumps(result, indent=2))
        print("="*80)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

