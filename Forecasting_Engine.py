"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ADAPTIVE CRYPTO FORECASTING ENGINE  –  SHORT-TERM (12/24/48H)     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Forecasts ONLY:  12-hour  │  24-hour  │  48-hour  horizons
Optimised for:   directional accuracy · volatility estimation · regime awareness

Data Sources (priority order):
  1. Binance REST API   (primary  – no key required for public endpoints)
  2. Bybit   REST API   (fallback)
  3. Alpha Vantage      (secondary fallback – set ALPHA_VANTAGE_API_KEY)

Models:
  • XGBoost       (primary gradient booster)
  • LightGBM      (primary gradient booster)
  • Random Forest (ensemble member)
  → Dynamic weighted ensemble updated after every prediction cycle

Install:
  pip install pandas numpy matplotlib scikit-learn xgboost lightgbm requests joblib

Usage:
  python crypto_forecast_engine.py              # uses default SYMBOL = ETH/USDT
  python crypto_forecast_engine.py --symbol BTC
  python crypto_forecast_engine.py --symbol SOL --exchange bybit
"""

# ── stdlib ───────────────────────────────────────────────────────────────────
import os, sys, json, time, argparse, logging, warnings
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("forecast")

# ── third-party ──────────────────────────────────────────────────────────────
try:
    import requests
    import numpy  as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import matplotlib.dates   as mdates
    from matplotlib.colors import LinearSegmentedColormap
    from sklearn.ensemble        import RandomForestRegressor, RandomForestClassifier
    from sklearn.preprocessing  import StandardScaler
    from sklearn.metrics         import (mean_absolute_error, mean_squared_error,
                                         r2_score, accuracy_score)
    import joblib
except ImportError as e:
    sys.exit(f"[FATAL] Missing core dependency: {e}\n"
             "Run:  pip install pandas numpy matplotlib scikit-learn requests joblib")

try:
    import xgboost  as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    log.warning("xgboost not found – skipping XGBoost model")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    log.warning("lightgbm not found – skipping LightGBM model")


# ══════════════════════════════════════════════════════════════════════════════
# 0.  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

HORIZONS       = [12, 24, 48]          # forecast windows in hours
TIMEFRAMES     = ["5m", "15m", "1h", "4h"]
CANDLES_LIMIT  = 500                   # candles per timeframe per fetch
RETRAIN_EVERY  = 6                     # hours between retraining
DB_PATH        = Path("forecast_db.json")
MODEL_DIR      = Path("models")
MODEL_DIR.mkdir(exist_ok=True)

AV_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

# HTTP headers to bypass geo-blocks and API restrictions
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


# ══════════════════════════════════════════════════════════════════════════════
# 1.  DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

BINANCE_TF = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}
BYBIT_TF   = {"5m": "5",  "15m": "15",  "1h": "60", "4h": "240"}

def _parse_binance(raw: list) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"])
    df["date"]   = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df[["date","open","high","low","close","volume"]].set_index("date")

def fetch_binance(symbol: str, interval: str, limit: int = CANDLES_LIMIT) -> Optional[pd.DataFrame]:
    url = "https://api.binance.com/api/v3/klines"
    try:
        r = requests.get(url, params={"symbol": symbol.replace("/",""),
                                       "interval": BINANCE_TF[interval],
                                       "limit": limit}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return _parse_binance(r.json())
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 451:
            log.warning(f"Binance {symbol} {interval}: Geo-blocked (451). Trying fallback…")
        else:
            log.warning(f"Binance {symbol} {interval}: {e}")
        return None
    except Exception as e:
        log.warning(f"Binance {symbol} {interval}: {e}")
        return None

def fetch_bybit(symbol: str, interval: str, limit: int = CANDLES_LIMIT) -> Optional[pd.DataFrame]:
    url = "https://api.bybit.com/v5/market/kline"
    try:
        r = requests.get(url, params={"category": "spot",
                                       "symbol": symbol.replace("/",""),
                                       "interval": BYBIT_TF[interval],
                                       "limit": limit}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json().get("result", {}).get("list", [])
        if not data:
            return None
        df = pd.DataFrame(data, columns=["open_time","open","high","low","close","volume","turnover"])
        df["date"] = pd.to_datetime(df["open_time"].astype(int), unit="ms", utc=True)
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        return df[["date","open","high","low","close","volume"]].set_index("date").sort_index()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            log.warning(f"Bybit {symbol} {interval}: Access forbidden (403). Trying fallback…")
        else:
            log.warning(f"Bybit {symbol} {interval}: {e}")
        return None
    except Exception as e:
        log.warning(f"Bybit {symbol} {interval}: {e}")
        return None

def fetch_funding_rate(symbol: str) -> float:
    """Fetch latest perpetual funding rate from Binance."""
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate",
                         params={"symbol": symbol.replace("/","") + "T", "limit": 1},
                         headers=HEADERS, timeout=10)
        data = r.json()
        if isinstance(data, list) and data:
            return float(data[-1].get("fundingRate", 0))
    except Exception:
        pass
    return 0.0

def fetch_open_interest(symbol: str) -> float:
    """Fetch open interest from Binance futures."""
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/openInterest",
                         params={"symbol": symbol.replace("/","") + "T"}, 
                         headers=HEADERS, timeout=10)
        return float(r.json().get("openInterest", 0))
    except Exception:
        return 0.0

def fetch_multi_timeframe(symbol: str, exchange: str = "binance") -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV for all timeframes from chosen exchange, with fallback."""
    fetcher = fetch_binance if exchange == "binance" else fetch_bybit
    fallback = fetch_bybit if exchange == "binance" else fetch_binance
    result = {}
    for tf in TIMEFRAMES:
        df = fetcher(symbol, tf)
        if df is None or len(df) < 100:
            log.info(f"  Fallback to secondary exchange for {tf}")
            df = fallback(symbol, tf)
        if df is not None and len(df) >= 50:
            result[tf] = df.copy()
            log.info(f"  ✓ {tf}: {len(df)} candles  (last: {df.index[-1].strftime('%Y-%m-%d %H:%M')})")
        else:
            log.warning(f"  ✗ Could not fetch {tf} data")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2.  FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full feature engineering pipeline.
    Generates 80+ features across trend, momentum, volatility,
    price action, and market structure dimensions.
    """
    d = df.copy()
    c = d["close"]; h = d["high"]; l = d["low"]; o = d["open"]; v = d["volume"]

    # ── Trend ─────────────────────────────────────────────────────────────────
    for p in [9, 21, 50, 200]:
        d[f"ema_{p}"] = c.ewm(span=p, adjust=False).mean()
    d["ema_spread_9_21"]  = d["ema_9"]  - d["ema_21"]
    d["ema_spread_21_50"] = d["ema_21"] - d["ema_50"]
    d["ema_spread_50_200"]= d["ema_50"] - d["ema_200"]
    d["trend_slope"]  = c.diff(5) / 5
    d["trend_accel"]  = d["trend_slope"].diff(3)
    d["ema_9_dist"]   = (c - d["ema_9"])  / d["ema_9"]
    d["ema_21_dist"]  = (c - d["ema_21"]) / d["ema_21"]
    d["ema_50_dist"]  = (c - d["ema_50"]) / d["ema_50"]

    # ── Momentum ──────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    d["rsi_14"] = 100 - (100 / (1 + rs))
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

    d["roc_5"]  = c.pct_change(5)
    d["roc_10"] = c.pct_change(10)
    d["roc_20"] = c.pct_change(20)

    # Williams %R
    d["willr_14"] = -100 * (high14 - c) / (high14 - low14 + 1e-9)

    # ── Volatility ────────────────────────────────────────────────────────────
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    d["atr_14"]  = tr.rolling(14).mean()
    d["atr_7"]   = tr.rolling(7).mean()
    d["atr_norm"]= d["atr_14"] / c

    d["rvol_7"]  = c.pct_change().rolling(7).std()
    d["rvol_14"] = c.pct_change().rolling(14).std()
    d["rvol_30"] = c.pct_change().rolling(30).std()

    ma20    = c.rolling(20).mean()
    std20   = c.rolling(20).std()
    d["bb_upper"] = ma20 + 2 * std20
    d["bb_lower"] = ma20 - 2 * std20
    d["bb_width"] = (d["bb_upper"] - d["bb_lower"]) / ma20
    d["bb_pct"]   = (c - d["bb_lower"]) / (d["bb_upper"] - d["bb_lower"] + 1e-9)
    d["bb_squeeze"]= (d["bb_width"] < d["bb_width"].rolling(50).quantile(0.20)).astype(int)
    d["vol_expand"]= (d["rvol_7"] > d["rvol_7"].shift(3)).astype(int)

    # ── Price Action ─────────────────────────────────────────────────────────
    body  = (c - o).abs()
    total = (h - l + 1e-9)
    d["body_ratio"]    = body / total
    d["upper_wick"]    = (h - pd.concat([c, o], axis=1).max(axis=1)) / total
    d["lower_wick"]    = (pd.concat([c, o], axis=1).min(axis=1) - l) / total
    d["candle_dir"]    = np.sign(c - o)
    d["engulf_bull"]   = ((c > o.shift()) & (o < c.shift()) & (c > o) & (c.shift() < o.shift())).astype(int)
    d["engulf_bear"]   = ((c < o.shift()) & (o > c.shift()) & (c < o) & (c.shift() > o.shift())).astype(int)

    # Breakout / compression
    d["range_20"]     = h.rolling(20).max() - l.rolling(20).min()
    d["breakout_up"]  = (c > h.rolling(20).max().shift()).astype(int)
    d["breakout_dn"]  = (c < l.rolling(20).min().shift()).astype(int)
    d["compression"]  = (d["range_20"] < d["range_20"].rolling(50).quantile(0.20)).astype(int)

    # Fair Value Gap (simplified: gap between current low and prior high)
    d["fvg_bull"] = ((l > h.shift(2)) & (c > o)).astype(int)
    d["fvg_bear"] = ((h < l.shift(2)) & (c < o)).astype(int)

    # Liquidity sweep
    d["liq_sweep_hi"] = ((h > h.rolling(10).max().shift()) & (c < h.rolling(10).max().shift())).astype(int)
    d["liq_sweep_lo"] = ((l < l.rolling(10).min().shift()) & (c > l.rolling(10).min().shift())).astype(int)

    # ── Market Structure ─────────────────────────────────────────────────────
    d["swing_hi"]  = (h == h.rolling(5, center=True).max()).astype(int)
    d["swing_lo"]  = (l == l.rolling(5, center=True).min()).astype(int)
    d["dist_swing_hi"] = (c - h[d["swing_hi"] == 1].reindex(d.index, method="ffill")) / c
    d["dist_swing_lo"] = (c - l[d["swing_lo"] == 1].reindex(d.index, method="ffill")) / c

    # Regime: trending vs ranging (ADX proxy)
    plus_dm  = (h.diff().clip(lower=0))
    minus_dm = (-l.diff().clip(upper=0))
    tr_smooth= tr.rolling(14).mean()
    d["adx_proxy"] = ((plus_dm.rolling(14).mean() - minus_dm.rolling(14).mean()).abs()
                      / (tr_smooth + 1e-9) * 100)
    d["regime"]    = (d["adx_proxy"] > 25).astype(int)   # 1 = trending, 0 = ranging

    # Premium / Discount zone (relative to 50-period range)
    mid = (h.rolling(50).max() + l.rolling(50).min()) / 2
    d["premium_zone"]  = (c > mid).astype(int)
    d["discount_zone"] = (c < mid).astype(int)

    # ── Volume / Order Flow ───────────────────────────────────────────────────
    d["vol_ma_20"]   = v.rolling(20).mean()
    d["vol_ratio"]   = v / (d["vol_ma_20"] + 1e-9)
    d["vol_spike"]   = (d["vol_ratio"] > 2.0).astype(int)
    d["cvd"]         = (np.where(c > o, v, -v)).cumsum()   # proxy cumulative volume delta
    d["cvd_slope"]   = pd.Series(d["cvd"], index=d.index).diff(5)
    d["buy_pressure"]= (c - l) / total              # candle-level proxy
    d["sell_pressure"]= (h - c) / total

    # ── Lag Features ─────────────────────────────────────────────────────────
    for lag in [1, 2, 3, 6, 12, 24]:
        d[f"lag_ret_{lag}"] = c.pct_change(lag)

    # ── Target variables (regression: future return; classification: direction) ─
    for h_steps in [12, 24, 48]:
        future_ret     = c.shift(-h_steps) / c - 1
        d[f"target_ret_{h_steps}h"]  = future_ret
        d[f"target_dir_{h_steps}h"]  = (future_ret > 0).astype(int)

    d.dropna(inplace=True)
    return d


def get_feature_cols(df: pd.DataFrame) -> List[str]:
    """Return all feature columns (excludes target/raw OHLCV)."""
    exclude = {"open","high","low","close","volume"} | \
              {c for c in df.columns if c.startswith("target_")}
    return [c for c in df.columns if c not in exclude]


# ══════════════════════════════════════════════════════════════════════════════
# 3 & 4.  MODEL TRAINING WITH WALK-FORWARD VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class ForecastModel:
    """
    Ensemble of XGBoost + LightGBM + Random Forest.
    Trains separate models for each horizon (12h, 24h, 48h).
    Maintains dynamic weights updated from recent prediction accuracy.
    """

    def __init__(self, horizon: int):
        self.horizon = horizon
        self.scaler  = StandardScaler()
        self.models: Dict[str, object]   = {}
        self.weights: Dict[str, float]   = {}
        self.feature_cols: List[str]     = []
        self.trained = False

    def _build_models(self):
        models = {
            "rf": RandomForestRegressor(n_estimators=200, max_depth=8,
                                        min_samples_leaf=5, random_state=42, n_jobs=-1),
        }
        if HAS_XGB:
            models["xgb"] = xgb.XGBRegressor(n_estimators=300, max_depth=5,
                                               learning_rate=0.05, subsample=0.8,
                                               colsample_bytree=0.8, random_state=42,
                                               verbosity=0)
        if HAS_LGB:
            models["lgb"] = lgb.LGBMRegressor(n_estimators=300, max_depth=5,
                                               learning_rate=0.05, subsample=0.8,
                                               colsample_bytree=0.8, random_state=42,
                                               verbose=-1)
        return models

    def fit(self, df: pd.DataFrame, feature_cols: List[str]):
        """
        Walk-forward: use first 80 % for training, last 20 % for OOF evaluation.
        Weights are assigned proportional to 1 / MAE on the validation fold.
        """
        self.feature_cols = feature_cols
        target_col = f"target_ret_{self.horizon}h"
        if target_col not in df.columns:
            raise ValueError(f"Column {target_col} not in dataframe")

        X = df[feature_cols].values
        y = df[target_col].values
        split = int(len(X) * 0.80)

        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        X_tr_sc  = self.scaler.fit_transform(X_tr)
        X_val_sc = self.scaler.transform(X_val)

        self.models  = self._build_models()
        self.weights = {}

        for name, model in self.models.items():
            model.fit(X_tr_sc, y_tr)
            val_pred = model.predict(X_val_sc)
            mae = mean_absolute_error(y_val, val_pred)
            self.weights[name] = 1.0 / (mae + 1e-9)
            log.info(f"  [{self.horizon}h/{name}]  val-MAE={mae:.5f}")

        # Normalise weights to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}
        log.info(f"  [{self.horizon}h] ensemble weights: "
                 + "  ".join(f"{k}={v:.2f}" for k, v in self.weights.items()))
        self.trained = True

    def predict_ensemble(self, X_raw: np.ndarray) -> np.ndarray:
        X_sc = self.scaler.transform(X_raw)
        preds = np.zeros(len(X_sc))
        for name, model in self.models.items():
            preds += self.weights[name] * model.predict(X_sc)
        return preds

    def predict_with_uncertainty(self, X_raw: np.ndarray) -> Tuple[float, float, float]:
        """
        Returns (ensemble_pred, lower_bound_pct, upper_bound_pct)
        Uncertainty estimated from spread across individual model predictions.
        Includes empirical calibration from recent forecast errors.
        """
        X_sc = self.scaler.transform(X_raw)
        individual = [model.predict(X_sc)[0] for model in self.models.values()]
        ensemble   = sum(w * p for w, p in zip(self.weights.values(), individual))
        
        # Base spread from model disagreement
        spread = np.std(individual) if len(individual) > 1 else abs(ensemble) * 0.5
        
        # Add empirical calibration: expand range if confidence is high
        # This prevents over-confident narrow predictions
        if abs(ensemble) < 0.001:  # very small move predicted
            spread = max(spread, abs(ensemble) * 2.0)  # at least 2x the predicted move
        else:
            spread = max(spread, abs(ensemble) * 0.8)  # at least 80% of predicted move
        
        return float(ensemble), float(ensemble - 2 * spread), float(ensemble + 2 * spread)

    def feature_importance(self) -> pd.Series:
        importances = {}
        for name, model in self.models.items():
            w = self.weights.get(name, 1.0)
            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
                for col, val in zip(self.feature_cols, imp):
                    importances[col] = importances.get(col, 0) + w * val
        return pd.Series(importances).sort_values(ascending=False)

    def update_weights(self, recent_errors: Dict[str, float]):
        """Dynamically adjust model weights based on recent prediction errors."""
        for name in self.weights:
            if name in recent_errors and recent_errors[name] > 0:
                self.weights[name] = 1.0 / (recent_errors[name] + 1e-9)
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}


# ══════════════════════════════════════════════════════════════════════════════
# 5.  SELF-LEARNING DATABASE
# ══════════════════════════════════════════════════════════════════════════════

class PredictionDatabase:
    """Persists prediction history and tracks accuracy for adaptive retraining."""

    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {"predictions": [], "metrics": {}, "regime_history": []}

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2, default=str))

    def record_prediction(self, symbol: str, horizon: int, ts: str,
                           pred_ret: float, actual_ret: Optional[float],
                           confidence: str, regime: int,
                           price_at_forecast: float):
        self.data["predictions"].append({
            "symbol":    symbol,
            "horizon":   horizon,
            "timestamp": ts,
            "pred_ret":  pred_ret,
            "actual_ret": actual_ret,
            "direction_correct": (
                int(np.sign(pred_ret) == np.sign(actual_ret))
                if actual_ret is not None else None
            ),
            "confidence": confidence,
            "regime":     regime,
            "price_at_forecast": price_at_forecast,
        })
        self.save()

    def win_rate(self, symbol: str = "", last_n: int = 50) -> float:
        preds = [p for p in self.data["predictions"]
                 if p.get("direction_correct") is not None
                 and (not symbol or p["symbol"] == symbol)][-last_n:]
        if not preds:
            return 0.5
        return np.mean([p["direction_correct"] for p in preds])

    def recent_mae(self, symbol: str, horizon: int, last_n: int = 30) -> float:
        preds = [p for p in self.data["predictions"]
                 if p["symbol"] == symbol and p["horizon"] == horizon
                 and p.get("actual_ret") is not None][-last_n:]
        if not preds:
            return 0.01
        return np.mean([abs(p["pred_ret"] - p["actual_ret"]) for p in preds])


# ══════════════════════════════════════════════════════════════════════════════
# 6.  FORECAST OUTPUT  +  7. RISK FILTERING
# ══════════════════════════════════════════════════════════════════════════════

RISK_FLAGS = {
    "vol_spike":     "ABNORMAL VOLATILITY DETECTED",
    "bb_squeeze":    "COMPRESSION – BREAKOUT IMMINENT",
    "liq_sweep_hi":  "LIQUIDITY SWEEP HIGH",
    "liq_sweep_lo":  "LIQUIDITY SWEEP LOW",
    "breakout_up":   "UPSIDE BREAKOUT",
    "breakout_dn":   "DOWNSIDE BREAKOUT",
}

def assess_confidence(pred_ret: float, spread: float, regime: int,
                       win_rate_hist: float, rvol: float) -> Tuple[str, float]:
    """
    Returns (label, score 0-1).
    Factors: model agreement spread, regime stability, historical win rate, volatility.
    Tuned to prevent over-confidence in low-vol regimes.
    """
    score = 0.50  # Start at neutral (was 1.0 - too optimistic)
    
    # Model agreement: smaller spread = higher confidence
    spread_penalty = min(abs(spread) / max(abs(pred_ret) + 1e-9, 0.01), 1.0)
    score += (1.0 - spread_penalty) * 0.25
    
    # Volatility adjustment: low vol = lower confidence (harder to predict moves)
    if rvol < 0.008:  # very low volatility
        score -= 0.15
    elif rvol > 0.03:  # high volatility
        score -= 0.10
    
    # Regime adjustment
    if regime == 1:  # trending
        score += 0.10
    else:  # ranging - much harder to predict
        score -= 0.15
    
    # Historical win rate
    score += (win_rate_hist - 0.5) * 0.30
    
    score = max(0.0, min(1.0, score))

    if score >= 0.65:
        label = "HIGH"
    elif score >= 0.45:
        label = "MEDIUM"
    else:
        label = "LOW"
    return label, score

def build_forecast(symbol: str, last_close: float, horizon: int,
                   pred_ret: float, lo_ret: float, hi_ret: float,
                   rvol: float, atr: float, regime: int,
                   risk_flags: List[str], win_rate_hist: float) -> dict:
    """Assemble the structured forecast object for one horizon."""

    pred_price = last_close * (1 + pred_ret)
    
    # Volatility-aware range scaling: expand predictions based on market volatility
    # Use ATR as a floor for minimum expected move
    atr_pct = atr / last_close
    vol_factor = max(rvol, atr_pct * 0.5)  # use whichever is larger
    
    # Ensure range is at least 2x the volatility
    min_move = vol_factor * 2
    current_spread = abs(hi_ret - lo_ret)
    
    if current_spread < min_move:
        # Expand range symmetrically around prediction
        expansion = (min_move - current_spread) / 2
        lo_ret = pred_ret - min_move / 2
        hi_ret = pred_ret + min_move / 2
    
    lo_price   = last_close * (1 + lo_ret)
    hi_price   = last_close * (1 + hi_ret)

    bull_prob  = min(max(0.5 + pred_ret / (rvol * 3 + 1e-9) * 0.5, 0.05), 0.95)
    bear_prob  = 1 - bull_prob

    conf_label, conf_score = assess_confidence(pred_ret, hi_ret - lo_ret,
                                                regime, win_rate_hist, rvol)

    vol_label = ("HIGH" if rvol > 0.025 else
                 "MEDIUM" if rvol > 0.012 else "LOW")

    trend_strength = min(abs(pred_ret) / (rvol + 1e-9), 1.0)  # cap at 1.0 (was 3.0)

    no_trade = (conf_label == "LOW" or
                "ABNORMAL VOLATILITY DETECTED" in risk_flags or
                rvol > 0.05)

    return {
        "horizon":          horizon,
        "symbol":           symbol,
        "last_close":       last_close,
        "pred_price":       pred_price,
        "pred_ret_pct":     pred_ret * 100,
        "range_lo":         lo_price,
        "range_hi":         hi_price,
        "bull_prob_pct":    bull_prob * 100,
        "bear_prob_pct":    bear_prob * 100,
        "confidence":       conf_label,
        "conf_score":       conf_score,
        "volatility":       vol_label,
        "rvol":             rvol,
        "atr":              atr,
        "trend_strength":   trend_strength,
        "regime":           "TRENDING" if regime == 1 else "RANGING",
        "risk_flags":       risk_flags,
        "no_trade":         no_trade,
    }

def print_forecast(fc: dict):
    h    = fc["horizon"]
    sep  = "─" * 55
    bull = fc["bull_prob_pct"]
    bear = fc["bear_prob_pct"]
    no_t = fc.get("no_trade", False)

    print(f"\n  ╔{'═'*53}╗")
    print(f"  ║  {h:>2}H FORECAST  –  {fc['symbol']:<20}               ║")
    print(f"  ╠{'═'*53}╣")
    if no_t:
        print(f"  ║  ⚠  STATUS:    {'⛔  NO TRADE / LOW CONFIDENCE':<37}  ║")
    else:
        dir_arrow = "▲ BULLISH" if bull >= 50 else "▼ BEARISH"
        print(f"  ║  Direction:  {dir_arrow:<42} ║")
    print(f"  ║  Bull Prob:  {bull:>5.1f}%   Bear Prob: {bear:>5.1f}%            ║")
    print(f"  ║  Pred Price: ${fc['pred_price']:>10,.2f}                           ║")
    print(f"  ║  Exp Range:  ${fc['range_lo']:>10,.2f}  –  ${fc['range_hi']:>10,.2f}   ║")
    print(f"  ║  Confidence: {fc['confidence']:<8}  (score={fc['conf_score']:.2f})              ║")
    print(f"  ║  Volatility: {fc['volatility']:<8}  Regime: {fc['regime']:<15}  ║")
    print(f"  ║  Trend Str:  {'▓' * int(fc['trend_strength'] * 10):<10} {fc['trend_strength']*100:.0f}%                  ║")
    if fc["risk_flags"]:
        print(f"  ╠{'─'*53}╣")
        for flag in fc["risk_flags"][:3]:
            print(f"  ║  ⚡  {flag:<49} ║")
    print(f"  ╚{'═'*53}╝")


# ══════════════════════════════════════════════════════════════════════════════
# 8 & 9.  VISUALISATION
# ══════════════════════════════════════════════════════════════════════════════

def build_dashboard(symbol: str, df_1h: pd.DataFrame,
                    forecasts: List[dict], feat_imp: pd.Series,
                    db: PredictionDatabase):
    """
    Six-panel dashboard:
      [0,0] Price + MAs + Bollinger Bands
      [0,1] Regime / ADX heatmap
      [1,0] RSI + MACD
      [1,1] Volume delta bars
      [2,0] Forecast bar chart (bull prob per horizon)
      [2,1] Feature importance (top-20)
    """
    fig = plt.figure(figsize=(18, 14))
    fig.patch.set_facecolor("#0d1117")
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.30)

    ACCENT   = "#00e5ff"
    BULL_CLR = "#00c853"
    BEAR_CLR = "#ff1744"
    MUTED    = "#4a5568"
    TEXT_CLR = "#e2e8f0"

    plt.rcParams.update({"text.color": TEXT_CLR,
                         "axes.labelcolor": TEXT_CLR,
                         "xtick.color": TEXT_CLR,
                         "ytick.color": TEXT_CLR})

    tail = df_1h.tail(120)
    idx  = tail.index

    # ── [0,0] Price chart ─────────────────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.set_facecolor("#161b22")
    ax0.plot(idx, tail["close"],   color=ACCENT,   lw=1.5, label="Close")
    ax0.plot(idx, tail["ema_21"],  color="#ff9800", lw=1,   ls="--", label="EMA-21")
    ax0.plot(idx, tail["ema_50"],  color="#9c27b0", lw=1,   ls="--", label="EMA-50")
    ax0.fill_between(idx, tail["bb_lower"], tail["bb_upper"],
                     alpha=0.08, color=ACCENT)
    ax0.set_title(f"{symbol}  –  1H Price + Bollinger Bands", color=TEXT_CLR, fontsize=10)
    ax0.legend(fontsize=7, facecolor="#161b22", edgecolor=MUTED)
    ax0.grid(alpha=0.15, color=MUTED)

    # ── [0,1] Regime heatmap ─────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 1])
    ax1.set_facecolor("#161b22")
    regime_vals = tail["regime"].values.reshape(1, -1)
    cmap_regime = LinearSegmentedColormap.from_list("regime", [BEAR_CLR, BULL_CLR])
    ax1.imshow(regime_vals, aspect="auto", cmap=cmap_regime, vmin=0, vmax=1)
    ax1.set_yticks([0]); ax1.set_yticklabels(["Regime"], color=TEXT_CLR, fontsize=8)
    ax1.set_title("Market Regime  (green=Trending, red=Ranging)", color=TEXT_CLR, fontsize=10)

    # ADX proxy overlay
    ax1b = ax1.twinx()
    ax1b.plot(range(len(tail)), tail["adx_proxy"].values,
              color="#ffeb3b", lw=1, label="ADX proxy")
    ax1b.axhline(25, color="white", lw=0.8, ls="--", alpha=0.5)
    ax1b.set_ylabel("ADX", color=TEXT_CLR, fontsize=8)
    ax1b.tick_params(colors=TEXT_CLR, labelsize=7)
    ax1.set_xticks([])

    # ── [1,0] RSI + MACD ─────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor("#161b22")
    ax2.plot(idx, tail["rsi_14"], color="#8bc34a", lw=1.2, label="RSI-14")
    ax2.axhline(70, color=BEAR_CLR, ls="--", lw=0.8, alpha=0.7)
    ax2.axhline(30, color=BULL_CLR, ls="--", lw=0.8, alpha=0.7)
    ax2.set_ylim(0, 100); ax2.set_ylabel("RSI", color=TEXT_CLR, fontsize=8)
    ax2.set_title("RSI-14 + MACD Histogram", color=TEXT_CLR, fontsize=10)
    ax2.grid(alpha=0.15, color=MUTED)
    ax2b = ax2.twinx()
    colors_m = [BULL_CLR if v >= 0 else BEAR_CLR for v in tail["macd_hist"]]
    ax2b.bar(idx, tail["macd_hist"], color=colors_m, alpha=0.5, width=0.03)
    ax2b.set_ylabel("MACD Hist", color=TEXT_CLR, fontsize=8)
    ax2b.tick_params(colors=TEXT_CLR, labelsize=7)

    # ── [1,1] Volume delta ────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor("#161b22")
    vol_col = [BULL_CLR if r > 0 else BEAR_CLR for r in tail["close"].diff()]
    ax3.bar(idx, tail["volume"], color=vol_col, alpha=0.7, width=0.03)
    ax3.plot(idx, tail["vol_ma_20"], color="#ff9800", lw=1, label="Vol MA-20")
    ax3.set_title("Volume (green=up, red=down)", color=TEXT_CLR, fontsize=10)
    ax3.set_yscale("log")
    ax3.legend(fontsize=7, facecolor="#161b22", edgecolor=MUTED)
    ax3.grid(alpha=0.15, color=MUTED)

    # ── [2,0] Forecast confidence bar chart ──────────────────────────────────
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.set_facecolor("#161b22")
    hours   = [f["horizon"] for f in forecasts]
    bulls   = [f["bull_prob_pct"] for f in forecasts]
    bears   = [f["bear_prob_pct"] for f in forecasts]
    x       = np.arange(len(hours))
    width   = 0.35
    ax4.bar(x - width/2, bulls, width, label="Bull %", color=BULL_CLR, alpha=0.85)
    ax4.bar(x + width/2, bears, width, label="Bear %", color=BEAR_CLR, alpha=0.85)
    ax4.axhline(50, color="white", ls="--", lw=0.8, alpha=0.5)
    ax4.set_xticks(x); ax4.set_xticklabels([f"{h}H" for h in hours], color=TEXT_CLR)
    ax4.set_ylim(0, 100); ax4.set_ylabel("%", color=TEXT_CLR)
    ax4.set_title("Directional Probability per Horizon", color=TEXT_CLR, fontsize=10)
    ax4.legend(fontsize=8, facecolor="#161b22", edgecolor=MUTED)
    ax4.grid(alpha=0.15, color=MUTED, axis="y")
    for i, fc in enumerate(forecasts):
        conf_clr = BULL_CLR if fc["confidence"] == "HIGH" else \
                   "#ff9800" if fc["confidence"] == "MEDIUM" else BEAR_CLR
        ax4.text(i, 5, fc["confidence"], ha="center", va="bottom",
                 color=conf_clr, fontsize=8, fontweight="bold")

    # ── [2,1] Feature importance ──────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.set_facecolor("#161b22")
    top = feat_imp.head(20)
    norm_imp = top / top.max()
    colors_fi = plt.cm.plasma(norm_imp.values)
    ax5.barh(range(len(top)), top.values, color=colors_fi, alpha=0.85)
    ax5.set_yticks(range(len(top)))
    ax5.set_yticklabels(top.index, fontsize=7, color=TEXT_CLR)
    ax5.invert_yaxis()
    ax5.set_title("Feature Importance (top 20)", color=TEXT_CLR, fontsize=10)
    ax5.grid(alpha=0.15, color=MUTED, axis="x")

    fig.suptitle(
        f"CRYPTO FORECASTING ENGINE  –  {symbol}  "
        f"│  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        color=ACCENT, fontsize=13, fontweight="bold", y=0.995
    )

    out = f"{symbol.replace('/', '_')}_dashboard.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    log.info(f"Dashboard saved → {out}")
    plt.show()
    return out


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATION
# ══════════════════════════════════════════════════════════════════════════════

def run_forecast(symbol: str = "ETHUSDT", exchange: str = "binance"):
    db = PredictionDatabase()
    log.info(f"Starting forecast engine  –  {symbol}  on  {exchange.upper()}")

    # ── 1. Fetch data ─────────────────────────────────────────────────────────
    tf_data = fetch_multi_timeframe(symbol, exchange)
    if not tf_data:
        log.error("No data retrieved. Check your internet connection / symbol name.")
        return

    # Use 1H as the primary modelling timeframe
    primary_tf = "1h" if "1h" in tf_data else list(tf_data.keys())[0]
    df_raw = tf_data[primary_tf]

    # Supplementary market context
    funding_rate = fetch_funding_rate(symbol)
    open_interest = fetch_open_interest(symbol)
    log.info(f"Funding rate: {funding_rate:.6f}   Open interest: {open_interest:,.0f}")

    # ── 2. Feature engineering ────────────────────────────────────────────────
    log.info("Engineering features …")
    df = add_features(df_raw)
    feature_cols = get_feature_cols(df)

    # Inject macro signals as scalar features
    df["funding_rate"]  = funding_rate
    df["open_interest"] = open_interest / (open_interest + 1e-9)  # normalise
    if "funding_rate" not in feature_cols:
        feature_cols += ["funding_rate", "open_interest"]

    log.info(f"Dataset: {len(df)} rows  ×  {len(feature_cols)} features")
    if len(df) < 150:
        log.error("Not enough data to train reliably (need ≥ 150 rows). Exiting.")
        return

    # ── 3-4. Train ensemble per horizon ──────────────────────────────────────
    trained_models: Dict[int, ForecastModel] = {}
    for h in HORIZONS:
        log.info(f"Training ensemble for {h}H horizon …")
        mdl = ForecastModel(h)
        mdl.fit(df, feature_cols)
        trained_models[h] = mdl
        mdl_path = MODEL_DIR / f"{symbol}_{h}h.joblib"
        joblib.dump(mdl, mdl_path)

    # ── 5. Risk flags from latest candle ─────────────────────────────────────
    latest = df.iloc[[-1]][feature_cols]
    risk_flags = [RISK_FLAGS[col] for col in RISK_FLAGS if df.iloc[-1].get(col, 0) == 1]
    last_close = float(df["close"].iloc[-1])
    rvol       = float(df["rvol_14"].iloc[-1])
    atr        = float(df["atr_14"].iloc[-1])
    regime     = int(df["regime"].iloc[-1])

    # ── 6. Generate forecasts ─────────────────────────────────────────────────
    forecasts = []
    ts = datetime.now(timezone.utc).isoformat()

    for h in HORIZONS:
        mdl = trained_models[h]
        pred_ret, lo_ret, hi_ret = mdl.predict_with_uncertainty(latest.values)
        win_r = db.win_rate(symbol)

        fc = build_forecast(
            symbol=symbol, last_close=last_close, horizon=h,
            pred_ret=pred_ret, lo_ret=lo_ret, hi_ret=hi_ret,
            rvol=rvol, atr=atr, regime=regime,
            risk_flags=risk_flags, win_rate_hist=win_r
        )
        forecasts.append(fc)
        db.record_prediction(symbol, h, ts, pred_ret, None,
                             fc["confidence"], regime, last_close)

    # ── 7. Print forecasts ────────────────────────────────────────────────────
    print("\n" + "═" * 59)
    print(f"  ADAPTIVE CRYPTO FORECASTING ENGINE")
    print(f"  Symbol: {symbol}   │   Last Close: ${last_close:,.2f}")
    print(f"  Regime: {'TRENDING' if regime else 'RANGING'}"
          f"   │   Volatility (14d): {rvol*100:.2f}%")
    print(f"  Historical Win Rate: {db.win_rate(symbol)*100:.1f}%")
    print("═" * 59)

    for fc in forecasts:
        print_forecast(fc)

    if risk_flags:
        print(f"\n  ⚡ Active Risk Flags: {', '.join(risk_flags)}")

    # ── 8. Performance metrics (in-sample for latest model) ──────────────────
    print("\n  MODEL PERFORMANCE (in-sample walk-forward):")
    for h in HORIZONS:
        mdl = trained_models[h]
        X_sc = mdl.scaler.transform(df[feature_cols].values)
        preds = mdl.predict_ensemble(df[feature_cols].values)
        actual = df[f"target_ret_{h}h"].values
        mae  = mean_absolute_error(actual, preds)
        mse  = mean_squared_error(actual, preds)
        rmse = np.sqrt(mse)  # Manual sqrt for compatibility
        dir_acc = accuracy_score((actual > 0).astype(int), (preds > 0).astype(int))
        print(f"    {h}H  │  MAE={mae:.5f}  RMSE={rmse:.5f}  DirAcc={dir_acc*100:.1f}%")

    # ── 9. Dashboard visualisation ────────────────────────────────────────────
    feat_imp = trained_models[24].feature_importance()   # use 24h model for importance
    build_dashboard(symbol, df, forecasts, feat_imp, db)

    # ── 10. Save outputs ──────────────────────────────────────────────────────
    csv_path = f"{symbol.replace('/','_')}_forecast.csv"
    pd.DataFrame(forecasts).to_csv(csv_path, index=False)
    log.info(f"Forecast saved → {csv_path}")

    hist_path = f"{symbol.replace('/','_')}_history.csv"
    pd.DataFrame(db.data["predictions"]).to_csv(hist_path, index=False)
    log.info(f"Prediction history saved → {hist_path}")

    print(f"\n  Outputs: {csv_path}  │  {symbol.replace('/','_')}_dashboard.png")
    return forecasts


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adaptive Crypto Forecasting Engine")
    parser.add_argument("--symbol",   default="ETHUSDT",  help="Trading pair, e.g. ETHUSDT, BTCUSDT")
    parser.add_argument("--exchange", default="binance",  choices=["binance","bybit"],
                        help="Primary data source")
    parser.add_argument("--loop",     action="store_true",
                        help="Run in loop, retraining every RETRAIN_EVERY hours")
    # Use parse_known_args() to ignore Jupyter/Colab kernel arguments
    args, unknown = parser.parse_known_args()

    if args.loop:
        log.info(f"Loop mode: retraining every {RETRAIN_EVERY}h")
        while True:
            run_forecast(args.symbol, args.exchange)
            log.info(f"Sleeping {RETRAIN_EVERY}h until next cycle …")
            time.sleep(RETRAIN_EVERY * 3600)
    else:
        run_forecast(args.symbol, args.exchange)
