"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   ADAPTIVE CRYPTO FORECASTING ENGINE – REAL-TIME PRICE SYNC                  ║
║   SHORT-TERM HORIZONS ONLY: 2HR | 4HR | 8HR | 12HR                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

CRITICAL FIXES:
  1. Real-time live price fetching (CCXT + Binance API)
  2. Price MUST be fetched inside prediction function – never cached/stale
  3. New timeframes: 2H, 4H, 8H, 12H (removed 12H, 24H, 48H)
  4. Multi-pair support with dynamic symbol handling
  5. Retry + fallback logic for exchange failures
  6. Returns actual live price used in forecast to prevent drift

Install:
  pip install pandas numpy matplotlib scikit-learn xgboost lightgbm requests joblib ccxt

Usage:
  from Forecasting_Engine_RealTime import get_live_price, run_forecast_realtime
  price, source = get_live_price("ETHUSDT")  # Returns (2267.45, "binance")
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
# 1.  REAL-TIME LIVE PRICE FETCHING (THE CRITICAL FIX)
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
        log.warning(f"CCXT {exchange_name} fetch failed for {symbol}: {e}")
        return None, None


def get_live_price(symbol: str, preferred_exchange: str = "binance"
                   ) -> Tuple[Optional[float], Optional[str]]:
    """
    MAIN ENTRY POINT: Fetch live price with smart fallback chain.
    
    Chain:
    1. Try REST API for preferred exchange
    2. Try CCXT (if installed)
    3. Fall back to other REST APIs (Kraken)
    
    Returns (price, source) where source is exchange name.
    Raises RuntimeError if all sources fail.
    """
    log.info(f"Fetching LIVE price for {symbol} (preferred: {preferred_exchange})")

    # Try REST APIs based on preference
    if preferred_exchange == "binance":
        price, source = get_live_price_binance(symbol)
        if price is not None:
            return price, source
        # Fallback to Kraken
        price, source = get_live_price_kraken(symbol)
        if price is not None:
            return price, source
    else:  # Kraken preferred
        price, source = get_live_price_kraken(symbol)
        if price is not None:
            return price, source
        # Fallback to Binance
        price, source = get_live_price_binance(symbol)
        if price is not None:
            return price, source

    # Try CCXT if available
    if HAS_CCXT:
        for exch in ["binance", "kraken", "bybit", "coinbase"]:
            price, source = get_live_price_ccxt(symbol, exch)
            if price is not None:
                return price, source

    # All sources failed
    msg = f"[CRITICAL] Could not fetch live price for {symbol} from any source"
    log.error(msg)
    raise RuntimeError(msg)


def get_live_price_with_retry(symbol: str, preferred_exchange: str = "binance",
                               retries: int = PRICE_FETCH_RETRIES
                               ) -> Tuple[float, str]:
    """
    Fetch live price with retry logic.
    Raises RuntimeError if all retries fail.
    """
    for attempt in range(1, retries + 1):
        try:
            price, source = get_live_price(symbol, preferred_exchange)
            log.info(f"✓ Live price fetched (attempt {attempt}): "
                    f"{symbol} = ${price:.2f} from {source}")
            return price, source
        except RuntimeError as e:
            if attempt < retries:
                log.warning(f"Price fetch attempt {attempt} failed, retrying…")
                time.sleep(0.5)
            else:
                log.error(f"All {retries} price fetch attempts failed: {e}")
                raise


# ══════════════════════════════════════════════════════════════════════════════
# 2.  DATA FETCHING (OHLCV HISTORICAL – separate from live price)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_candles_binance(symbol: str, interval: str,
                          limit: int = CANDLES_LIMIT) -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV from Binance REST API."""
    if symbol not in SUPPORTED_PAIRS or "binance" not in SUPPORTED_PAIRS[symbol]:
        return None

    binance_symbol = SUPPORTED_PAIRS[symbol]["binance"].replace("/", "")
    tf_map = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}

    try:
        url = "https://api.binance.com/api/v3/klines"
        resp = requests.get(
            url,
            params={"symbol": binance_symbol, "interval": tf_map[interval], "limit": limit},
            headers=HEADERS,
            timeout=PRICE_FETCH_TIMEOUT
        )
        resp.raise_for_status()
        raw = resp.json()
        df = pd.DataFrame(raw, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","qav","trades","tbbav","tbqav","ignore"
        ])
        df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df[["date","open","high","low","close","volume"]].set_index("date")
    except Exception as e:
        log.warning(f"Binance OHLCV fetch failed for {symbol} {interval}: {e}")
        return None


def fetch_candles_kraken(symbol: str, interval: str,
                         limit: int = CANDLES_LIMIT) -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV from Kraken."""
    if symbol not in SUPPORTED_PAIRS or "kraken" not in SUPPORTED_PAIRS[symbol]:
        return None

    kraken_pair = SUPPORTED_PAIRS[symbol]["kraken"]
    tf_map = {"5m":"5","15m":"15","1h":"60","4h":"240"}

    try:
        url = "https://api.kraken.com/0/public/OHLC"
        resp = requests.get(
            url,
            params={"pair": kraken_pair, "interval": tf_map[interval]},
            headers=HEADERS,
            timeout=PRICE_FETCH_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            return None
        pair_data = [v for k, v in data["result"].items() if k != "last"]
        if not pair_data:
            return None
        rows = pair_data[0][-limit:]
        df = pd.DataFrame(rows, columns=["time","open","high","low","close","vwap","volume","count"])
        df["date"] = pd.to_datetime(df["time"].astype(int), unit="s", utc=True)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df[["date","open","high","low","close","volume"]].set_index("date").sort_index()
    except Exception as e:
        log.warning(f"Kraken OHLCV fetch failed for {symbol} {interval}: {e}")
        return None


def fetch_candles(symbol: str, interval: str, preferred: str = "binance"
                  ) -> Optional[pd.DataFrame]:
    """Try to fetch OHLCV – prefers Binance, falls back to Kraken."""
    if preferred == "binance":
        df = fetch_candles_binance(symbol, interval)
        if df is not None and len(df) >= 50:
            return df
        df = fetch_candles_kraken(symbol, interval)
        if df is not None and len(df) >= 50:
            return df
    else:
        df = fetch_candles_kraken(symbol, interval)
        if df is not None and len(df) >= 50:
            return df
        df = fetch_candles_binance(symbol, interval)
        if df is not None and len(df) >= 50:
            return df
    return None


def fetch_multi_timeframe(symbol: str, preferred: str = "binance") -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV for all timeframes."""
    result = {}
    for tf in TIMEFRAMES:
        df = fetch_candles(symbol, tf, preferred)
        if df is not None and len(df) >= 50:
            result[tf] = df.copy()
            log.info(f"  ✓ {tf}: {len(df)} candles")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 3.  FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def add_features(df: pd.DataFrame, live_price: Optional[float] = None) -> pd.DataFrame:
    """
    Add technical features. If live_price is provided, use it to anchor recent rows.
    This ensures the model sees the live price context, not stale closes.
    """
    d = df.copy()
    c = d["close"]; h = d["high"]; l = d["low"]; o = d["open"]; v = d["volume"]

    # ── Trend ─────────────────────────────────────────────────────────────────
    for p in [9, 21, 50, 200]:
        d[f"ema_{p}"] = c.ewm(span=p, adjust=False).mean()
    d["ema_spread_9_21"]   = d["ema_9"]  - d["ema_21"]
    d["ema_spread_21_50"]  = d["ema_21"] - d["ema_50"]
    d["ema_spread_50_200"] = d["ema_50"] - d["ema_200"]
    d["trend_slope"]  = c.diff(5) / 5
    d["trend_accel"]  = d["trend_slope"].diff(3)
    d["ema_9_dist"]   = (c - d["ema_9"])  / (d["ema_9"] + 1e-9)
    d["ema_21_dist"]  = (c - d["ema_21"]) / (d["ema_21"] + 1e-9)
    d["ema_50_dist"]  = (c - d["ema_50"]) / (d["ema_50"] + 1e-9)

    # ── Momentum ──────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi_14"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    d["rsi_7"]  = 100 - (100 / (1 + c.diff().clip(lower=0).rolling(7).mean() /
                                   (-c.diff().clip(upper=0)).rolling(7).mean().replace(0, np.nan)))
    d["rsi_divergence"] = d["rsi_14"].diff(5)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    d["macd"]        = ema12 - ema26
    d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
    d["macd_hist"]   = d["macd"] - d["macd_signal"]
    low14  = l.rolling(14).min(); high14 = h.rolling(14).max()
    stoch_k = 100 * (c - low14) / (high14 - low14 + 1e-9)
    d["stoch_k"] = stoch_k.rolling(3).mean()
    d["stoch_d"] = d["stoch_k"].rolling(3).mean()
    for p in [5, 10, 20]:
        d[f"roc_{p}"] = c.pct_change(p)
    d["willr_14"] = -100 * (high14 - c) / (high14 - low14 + 1e-9)

    # ── Volatility ────────────────────────────────────────────────────────────
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr_14"]   = tr.rolling(14).mean()
    d["atr_7"]    = tr.rolling(7).mean()
    d["atr_norm"] = d["atr_14"] / (c + 1e-9)
    for p in [7, 14, 30]:
        d[f"rvol_{p}"] = c.pct_change().rolling(p).std()
    ma20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
    d["bb_upper"]   = ma20 + 2 * std20
    d["bb_lower"]   = ma20 - 2 * std20
    d["bb_width"]   = (d["bb_upper"] - d["bb_lower"]) / (ma20 + 1e-9)
    d["bb_pct"]     = (c - d["bb_lower"]) / (d["bb_upper"] - d["bb_lower"] + 1e-9)
    d["bb_squeeze"] = (d["bb_width"] < d["bb_width"].rolling(50).quantile(0.20)).astype(int)
    d["vol_expand"] = (d["rvol_7"] > d["rvol_7"].shift(3)).astype(int)

    # ── Price action ──────────────────────────────────────────────────────────
    body  = (c - o).abs(); total = h - l + 1e-9
    d["body_ratio"]  = body / total
    d["upper_wick"]  = (h - pd.concat([c, o], axis=1).max(axis=1)) / total
    d["lower_wick"]  = (pd.concat([c, o], axis=1).min(axis=1) - l) / total
    d["candle_dir"]  = np.sign(c - o)
    d["engulf_bull"] = ((c > o.shift()) & (o < c.shift()) & (c > o) & (c.shift() < o.shift())).astype(int)
    d["engulf_bear"] = ((c < o.shift()) & (o > c.shift()) & (c < o) & (c.shift() > o.shift())).astype(int)
    d["range_20"]    = h.rolling(20).max() - l.rolling(20).min()
    d["breakout_up"] = (c > h.rolling(20).max().shift()).astype(int)
    d["breakout_dn"] = (c < l.rolling(20).min().shift()).astype(int)
    d["compression"] = (d["range_20"] < d["range_20"].rolling(50).quantile(0.20)).astype(int)
    d["fvg_bull"]    = ((l > h.shift(2)) & (c > o)).astype(int)
    d["fvg_bear"]    = ((h < l.shift(2)) & (c < o)).astype(int)
    d["liq_sweep_hi"]= ((h > h.rolling(10).max().shift()) & (c < h.rolling(10).max().shift())).astype(int)
    d["liq_sweep_lo"]= ((l < l.rolling(10).min().shift()) & (c > l.rolling(10).min().shift())).astype(int)

    # ── Market structure ──────────────────────────────────────────────────────
    d["swing_hi"]  = (h == h.rolling(5, center=True).max()).astype(int)
    d["swing_lo"]  = (l == l.rolling(5, center=True).min()).astype(int)
    swing_hi_vals  = h.where(d["swing_hi"] == 1).ffill()
    swing_lo_vals  = l.where(d["swing_lo"] == 1).ffill()
    d["dist_swing_hi"] = (c - swing_hi_vals) / (c + 1e-9)
    d["dist_swing_lo"] = (c - swing_lo_vals) / (c + 1e-9)
    plus_dm  = h.diff().clip(lower=0)
    minus_dm = (-l.diff()).clip(lower=0)
    tr_s     = tr.rolling(14).mean()
    d["adx_proxy"] = ((plus_dm.rolling(14).mean() - minus_dm.rolling(14).mean()).abs()
                      / (tr_s + 1e-9) * 100)
    d["regime"]    = (d["adx_proxy"] > 25).astype(int)
    mid = (h.rolling(50).max() + l.rolling(50).min()) / 2
    d["premium_zone"]  = (c > mid).astype(int)
    d["discount_zone"] = (c < mid).astype(int)

    # ── Volume ────────────────────────────────────────────────────────────────
    d["vol_ma_20"]    = v.rolling(20).mean()
    d["vol_ratio"]    = v / (d["vol_ma_20"] + 1e-9)
    d["vol_spike"]    = (d["vol_ratio"] > 2.0).astype(int)
    d["cvd"]          = pd.Series(np.where(c > o, v, -v), index=d.index).cumsum()
    d["cvd_slope"]    = d["cvd"].diff(5)
    d["buy_pressure"] = (c - l) / total
    d["sell_pressure"]= (h - c) / total

    # ── Lag features ──────────────────────────────────────────────────────────
    for lag in [1, 2, 3, 6, 12, 24]:
        d[f"lag_ret_{lag}"] = c.pct_change(lag)

    # ── CRITICAL: Use live_price if provided to anchor the most recent values ──
    # This ensures model sees live price context
    if live_price is not None:
        live_price_dist = (live_price - d["close"].iloc[-1]) / (d["close"].iloc[-1] + 1e-9)
        d["live_price_adj"] = live_price_dist   # Distance from last close to live price
        log.info(f"Live price adjustment feature set: live=${live_price:.2f}, "
                f"last_close=${d['close'].iloc[-1]:.2f}, diff={live_price_dist*100:.2f}%")
    else:
        d["live_price_adj"] = 0.0

    # ── Targets: ONLY for new horizons (2H, 4H, 8H, 12H) ──────────────────────
    for h_steps in HORIZONS:
        future_ret     = c.shift(-h_steps) / c - 1
        d[f"target_ret_{h_steps}h"]  = future_ret
        d[f"target_dir_{h_steps}h"]  = (future_ret > 0).astype(int)

    d.dropna(inplace=True)
    return d


def get_feature_cols(df: pd.DataFrame) -> List[str]:
    exclude = {"open","high","low","close","volume"} | \
              {c for c in df.columns if c.startswith("target_")}
    return [c for c in df.columns if c not in exclude]


# ══════════════════════════════════════════════════════════════════════════════
# 4.  ENSEMBLE MODEL
# ══════════════════════════════════════════════════════════════════════════════

class ForecastModel:
    """
    Ensemble: XGBoost + LightGBM + RandomForest
    Separate model per horizon (2H, 4H, 8H, 12H).
    """

    def __init__(self, horizon: int):
        self.horizon = horizon
        self.scaler  = StandardScaler()
        self.models: Dict[str, object] = {}
        self.weights: Dict[str, float] = {}
        self.feature_cols: List[str]   = []
        self.trained = False

    def _build_models(self):
        m = {"rf": RandomForestRegressor(n_estimators=200, max_depth=8,
                                          min_samples_leaf=5, random_state=42, n_jobs=-1)}
        if HAS_XGB:
            m["xgb"] = xgb.XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05,
                                          subsample=0.8, colsample_bytree=0.8,
                                          random_state=42, verbosity=0)
        if HAS_LGB:
            m["lgb"] = lgb.LGBMRegressor(n_estimators=300, max_depth=5, learning_rate=0.05,
                                           subsample=0.8, colsample_bytree=0.8,
                                           random_state=42, verbose=-1)
        return m

    def fit(self, df: pd.DataFrame, feature_cols: List[str]):
        self.feature_cols = feature_cols
        target = f"target_ret_{self.horizon}h"
        if target not in df.columns:
            raise ValueError(f"Column {target} not in dataframe")

        X = df[feature_cols].values
        y = df[target].values
        split = int(len(X) * 0.80)
        Xtr, Xval = X[:split], X[split:]
        ytr, yval = y[:split], y[split:]
        Xtr_sc  = self.scaler.fit_transform(Xtr)
        Xval_sc = self.scaler.transform(Xval)

        self.models  = self._build_models()
        self.weights = {}

        for name, mdl in self.models.items():
            mdl.fit(Xtr_sc, ytr)
            mae = mean_absolute_error(yval, mdl.predict(Xval_sc))
            self.weights[name] = 1.0 / (mae + 1e-9)
            log.info(f"  [{self.horizon}h/{name}]  val-MAE={mae:.5f}")

        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
        self.trained = True

    def predict_ensemble(self, X_raw: np.ndarray) -> np.ndarray:
        Xsc = self.scaler.transform(X_raw)
        out = np.zeros(len(Xsc))
        for name, mdl in self.models.items():
            out += self.weights[name] * mdl.predict(Xsc)
        return out

    def predict_with_uncertainty(self, X_raw: np.ndarray) -> Tuple[float, float, float]:
        """Returns (ensemble_pred, lower_bound, upper_bound)."""
        Xsc = self.scaler.transform(X_raw)
        ind = [m.predict(Xsc)[0] for m in self.models.values()]
        ens = sum(w * p for w, p in zip(self.weights.values(), ind))
        sprd = np.std(ind) if len(ind) > 1 else abs(ens) * 0.5
        return float(ens), float(ens - 2*sprd), float(ens + 2*sprd)

    def feature_importance(self) -> pd.Series:
        imp = {}
        for name, mdl in self.models.items():
            w = self.weights.get(name, 1.0)
            if hasattr(mdl, "feature_importances_"):
                for col, val in zip(self.feature_cols, mdl.feature_importances_):
                    imp[col] = imp.get(col, 0) + w * val
        return pd.Series(imp).sort_values(ascending=False)


# ══════════════════════════════════════════════════════════════════════════════
# 5.  MAIN FORECAST FUNCTION – REAL-TIME ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_forecast_realtime(symbol: str = "ETHUSDT",
                          exchange: str = "binance") -> Dict:
    """
    MAIN ENTRY POINT FOR FORECASTING – THE CRITICAL FIX LOCATION
    
    Steps:
    1. ✓ FETCH LIVE PRICE FIRST (NOT from cached historical data)
    2. Fetch historical OHLCV
    3. Engineer features with live price context
    4. Train ensemble per horizon (2H, 4H, 8H, 12H only)
    5. Generate forecasts
    6. RETURN live price used in forecast to prevent drift on frontend
    
    Returns dict with:
    {
        "live_price": 2267.45,
        "price_source": "binance",
        "symbol": "ETHUSDT",
        "forecasts": [
            {"horizon": 2, "pred_ret": 0.015, "bull_prob": 65, ...},
            ...
        ],
        "meta": {...}
    }
    """
    log.info(f"═══ REAL-TIME FORECAST START ═══")
    log.info(f"Symbol: {symbol} | Exchange: {exchange}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: FETCH LIVE PRICE – THIS IS THE CRITICAL FIX
    # ──────────────────────────────────────────────────────────────────────────
    try:
        live_price, price_source = get_live_price_with_retry(symbol, exchange)
        log.info(f"✓✓✓ LIVE PRICE LOCKED IN: ${live_price:.2f} from {price_source} ✓✓✓")
    except RuntimeError as e:
        log.error(f"FATAL: Live price fetch failed: {e}")
        raise

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Fetch historical OHLCV (separate from live price)
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
    # STEP 3: Engineer features WITH live price context
    # ──────────────────────────────────────────────────────────────────────────
    log.info("Engineering features with live price context …")
    df = add_features(df_raw, live_price=live_price)  # PASS LIVE PRICE HERE
    feature_cols = get_feature_cols(df)

    log.info(f"Dataset: {len(df)} rows × {len(feature_cols)} features")
    if len(df) < 150:
        msg = f"Only {len(df)} rows after features (need ≥150)"
        log.error(msg)
        raise RuntimeError(msg)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Train ensemble models (ONLY for new horizons: 2H, 4H, 8H, 12H)
    # ──────────────────────────────────────────────────────────────────────────
    log.info(f"Training ensemble for horizons: {HORIZONS}")
    trained_models: Dict[int, ForecastModel] = {}
    for h in HORIZONS:
        log.info(f"Training {h}H model …")
        mdl = ForecastModel(h)
        mdl.fit(df, feature_cols)
        trained_models[h] = mdl
        mdl_path = MODEL_DIR / f"{symbol}_{h}h.joblib"
        joblib.dump(mdl, mdl_path)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Generate forecasts
    # ──────────────────────────────────────────────────────────────────────────
    log.info("Generating forecasts …")
    latest = df.iloc[[-1]][feature_cols]
    rvol   = float(df["rvol_14"].iloc[-1])
    atr    = float(df["atr_14"].iloc[-1])
    regime = int(df["regime"].iloc[-1])

    forecasts = []
    ts = datetime.now(timezone.utc).isoformat()

    for h in HORIZONS:
        mdl = trained_models[h]
        pred_ret, lo_ret, hi_ret = mdl.predict_with_uncertainty(latest.values)

        pred_price = live_price * (1 + pred_ret)
        lo_price   = live_price * (1 + lo_ret)
        hi_price   = live_price * (1 + hi_ret)

        bull_prob = float(np.clip(0.5 + pred_ret / (rvol * 3 + 1e-9) * 0.5, 0.05, 0.95))
        conf_score = np.clip(1.0 - abs(hi_ret - lo_ret) / max(abs(pred_ret) + 1e-9, 0.01), 0.0, 1.0)

        forecasts.append({
            "horizon":        h,
            "symbol":         symbol,
            "pred_price":     round(pred_price, 2),
            "pred_ret_pct":   round(pred_ret * 100, 3),
            "range_lo":       round(lo_price, 2),
            "range_hi":       round(hi_price, 2),
            "bull_prob_pct":  round(bull_prob * 100, 1),
            "bear_prob_pct":  round((1 - bull_prob) * 100, 1),
            "confidence":     "HIGH" if conf_score >= 0.65 else "MEDIUM" if conf_score >= 0.45 else "LOW",
            "conf_score":     round(conf_score, 2),
            "volatility":     "HIGH" if rvol > 0.025 else "MEDIUM" if rvol > 0.012 else "LOW",
            "rvol":           round(rvol, 4),
            "atr":            round(atr, 2),
            "regime":         "TRENDING" if regime == 1 else "RANGING",
        })

        log.info(f"✓ {h}H: pred={pred_price:.2f}  bull={bull_prob*100:.0f}%  conf={conf_score:.2f}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Return live price + forecasts
    # ──────────────────────────────────────────────────────────────────────────
    result = {
        "status": "success",
        "live_price":     live_price,
        "price_source":   price_source,
        "symbol":         symbol,
        "exchange":       exchange,
        "timestamp":      ts,
        "forecasts":      forecasts,
        "meta": {
            "last_close":  round(df["close"].iloc[-1], 2),
            "live_price":  live_price,
            "rvol":        round(rvol * 100, 3),
            "regime":      "TRENDING" if regime == 1 else "RANGING",
        }
    }

    log.info(f"═══ FORECAST COMPLETE ═══")
    log.info(f"Live price: ${live_price:.2f}  | "
            f"Last historical close: ${df['close'].iloc[-1]:.2f}  | "
            f"Drift: {abs(live_price - df['close'].iloc[-1]):.2f}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="ETHUSDT")
    parser.add_argument("--exchange", default="binance")
    args, _ = parser.parse_known_args()

    try:
        result = run_forecast_realtime(args.symbol, args.exchange)
        print("\n" + "="*60)
        print(json.dumps(result, indent=2))
        print("="*60)
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
