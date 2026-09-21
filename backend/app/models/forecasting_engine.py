"""
MarketFlux – Forecasting Engine
Loads the active ML model, runs inference, and builds a structured signal.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

from ..config.settings import MODEL_DIR
from ..models.feature_engineering import add_features, get_feature_cols
from ..models.rules_strategy import TradingRulesStrategy

log = logging.getLogger("marketflux.engine")

# ── Ensemble Model Class ──────────────────────────────────────────────────────

class InstitutionalForecastModel:
    """
    Ensemble ML model: RandomForest + XGBoost + LightGBM.
    Trained to predict the 2R/1R binary target.
    """

    def __init__(self, symbol: str, timeframe: str):
        self.symbol    = symbol
        self.timeframe = timeframe
        self.models: Dict = {}
        self.weights: Dict = {}
        self.scaler = None
        self.feature_cols: List[str] = []
        self.trained = False
        self.version = "untrained"
        self.training_date: Optional[datetime] = None

    def fit(self, X: np.ndarray, y: np.ndarray, feature_cols: List[str]) -> None:
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import precision_score

        self.feature_cols = feature_cols
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Calculate dynamic class weights for severe imbalance
        num_neg = len(y[y == 0])
        num_pos = len(y[y == 1])
        scale_pos_weight = num_neg / num_pos if num_pos > 0 else 1.0

        # Build ensemble
        self.models["rf"] = RandomForestClassifier(
            n_estimators=100, max_depth=12,
            min_samples_split=10, min_samples_leaf=5,
            class_weight="balanced",
            random_state=42, n_jobs=-1,
        )
        try:
            import xgboost as xgb
            self.models["xgb"] = xgb.XGBClassifier(
                n_estimators=100, max_depth=8,
                learning_rate=0.05, subsample=0.8,
                colsample_bytree=0.8, use_label_encoder=False,
                scale_pos_weight=scale_pos_weight,
                eval_metric="logloss", random_state=42, n_jobs=-1,
            )
        except ImportError:
            log.warning("xgboost not available")

        try:
            import lightgbm as lgb
            self.models["lgb"] = lgb.LGBMClassifier(
                n_estimators=100, max_depth=8,
                learning_rate=0.05, num_leaves=31,
                scale_pos_weight=scale_pos_weight,
                random_state=42, n_jobs=-1, verbose=-1,
            )
        except ImportError:
            log.warning("lightgbm not available")

        # Train all models
        for name, mdl in self.models.items():
            mdl.fit(X_scaled, y)
            log.info(f"  ✓ Trained {name}")

        # Weight by precision (better models get higher weight)
        precisions = {}
        for name, mdl in self.models.items():
            preds = mdl.predict(X_scaled)
            precisions[name] = precision_score(y, preds, zero_division=0)
        total = sum(precisions.values()) or 1.0
        self.weights = {k: v / total for k, v in precisions.items()}
        log.info(f"Model weights: {self.weights}")

        self.trained = True
        self.training_date = datetime.now(timezone.utc)
        self.version = f"v{self.training_date.strftime('%Y%m%d_%H%M')}"

    def predict_proba(self, X_raw: np.ndarray) -> float:
        """Return ensemble probability of a WIN (class 1)."""
        import warnings
        if not self.trained:
            raise RuntimeError("Model not trained")
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            X_scaled = self.scaler.transform(X_raw)
            prob = 0.0
            for name, mdl in self.models.items():
                w = self.weights.get(name, 1.0 / len(self.models))
                if hasattr(mdl, "predict_proba"):
                    prob += w * mdl.predict_proba(X_scaled)[0][1]
                else:
                    prob += w * float(mdl.predict(X_scaled)[0])
        return float(np.clip(prob, 0.0, 1.0))

    def save(self, path: Path) -> None:
        joblib.dump(self, path)
        log.info(f"Model saved → {path}")

    @staticmethod
    def load(path: Path) -> "InstitutionalForecastModel":
        mdl = joblib.load(path)
        log.info(f"Model loaded ← {path} (version={mdl.version})")
        return mdl


# ── Active Model Registry ─────────────────────────────────────────────────────

def _model_path(symbol: str, timeframe: str) -> Path:
    return MODEL_DIR / f"{symbol}_{timeframe}.joblib"


def load_active_model(symbol: str, timeframe: str) -> Optional[InstitutionalForecastModel]:
    path = _model_path(symbol, timeframe)
    if path.exists():
        try:
            return InstitutionalForecastModel.load(path)
        except Exception as e:
            log.warning(f"Could not load model from {path}: {e}")
    return None


# ── Confluence Scoring ────────────────────────────────────────────────────────

def calculate_confluence_score(row: pd.Series) -> Tuple[str, int, List[str]]:
    """
    Aggregate SMC/ICT signals into trade direction + confluence score.
    Returns (direction, score_0_to_100, active_signals).
    """
    signals: List[str] = []
    long_w  = 0.0
    short_w = 0.0

    def _add(condition: bool, label: str, long: float = 0.0, short: float = 0.0):
        nonlocal long_w, short_w
        if condition:
            signals.append(label)
            long_w  += long
            short_w += short

    _add(row.get("ema_alignment", 0) > 0.5,      "ema_bullish_stack",      long=2.0)
    _add(row.get("ema_alignment", 0) < -0.5,     "ema_bearish_stack",      short=2.0)
    _add(row.get("bullish_bos", 0) > 0.5,        "bullish_bos",            long=1.5)
    _add(row.get("bearish_bos", 0) > 0.5,        "bearish_bos",            short=1.5)
    _add(row.get("liquidity_sweep_bull", 0) > 0.5,"liquidity_sweep_bull",   long=1.5)
    _add(row.get("liquidity_sweep_bear", 0) > 0.5,"liquidity_sweep_bear",   short=1.5)
    _add(row.get("bullish_fvg", 0) > 0.5,        "bullish_fvg",            long=1.0)
    _add(row.get("bearish_fvg", 0) > 0.5,        "bearish_fvg",            short=1.0)
    _add(row.get("ob_signal", 0) > 0.5 and row.get("rsi_14", 50) < 40,
                                                   "ob_support",             long=1.5)
    _add(row.get("ob_signal", 0) > 0.5 and row.get("rsi_14", 50) > 60,
                                                   "ob_resistance",          short=1.5)
    _add(row.get("bullish_divergence", 0) > 0.5, "rsi_bullish_div",        long=1.5)
    _add(row.get("bearish_divergence", 0) > 0.5, "rsi_bearish_div",        short=1.5)
    _add(row.get("macd_bullish", 0) > 0.5,       "macd_bullish",           long=1.0)
    _add(row.get("macd_bullish", 0) < 0.5,       "macd_bearish",           short=1.0)
    _add(row.get("displacement", 0) > 0.5 and row.get("bullish", 0) > 0.5,
                                                   "displacement_bull",      long=1.0)
    _add(row.get("displacement", 0) > 0.5 and row.get("bullish", 0) < 0.5,
                                                   "displacement_bear",      short=1.0)
    _add(row.get("vol_spike", 0) > 0.5 and row.get("ret_1", 0) > 0.002,
                                                   "volume_spike_bull",      long=1.0)
    _add(row.get("vol_spike", 0) > 0.5 and row.get("ret_1", 0) < -0.002,
                                                   "volume_spike_bear",      short=1.0)
    _add(row.get("rsi_14", 50) < 40,              "rsi_oversold",           long=1.0)
    _add(row.get("rsi_14", 50) > 60,              "rsi_overbought",         short=1.0)
    _add(row.get("trend_strength", 0) > 0.5,     "trend_strength_bull",    long=1.0)
    _add(row.get("trend_strength", 0) < -0.5,    "trend_strength_bear",    short=1.0)
    _add(row.get("choch_signal", 0) > 0.5,       "choch",                  long=0.5, short=0.5)

    total = long_w + short_w
    if total < 0.1:
        return "NEUTRAL", 50, signals

    bull_prob = long_w / total
    score = int(bull_prob * 100)

    if long_w > short_w * 1.5:
        direction = "STRONG_LONG" if long_w >= 4 else "LONG"
    elif short_w > long_w * 1.5:
        direction = "STRONG_SHORT" if short_w >= 4 else "SHORT"
        score = 100 - score
    else:
        direction = "NEUTRAL"

    return direction, score, signals


# ── Trade Levels ──────────────────────────────────────────────────────────────

def calculate_trade_levels(row: pd.Series, direction: str, live_price: float, atr: float) -> Dict:
    """Calculate ATR-adjusted entry, stop-loss, and take-profit levels."""
    if direction in ("LONG", "STRONG_LONG"):
        entry  = max(float(row.get("support_1", live_price)), live_price - atr * 0.5)
        sl     = float(row.get("support_1", live_price - atr)) - atr * 0.5
        tp1    = float(row.get("resistance_1", live_price + atr))
        tp2    = tp1 + atr * 2
    elif direction in ("SHORT", "STRONG_SHORT"):
        entry  = min(float(row.get("resistance_1", live_price)), live_price + atr * 0.5)
        sl     = float(row.get("resistance_1", live_price + atr)) + atr * 0.5
        tp1    = float(row.get("support_1", live_price - atr))
        tp2    = tp1 - atr * 2
    else:
        entry  = live_price
        sl     = live_price - atr
        tp1    = live_price + atr
        tp2    = live_price + atr * 2

    risk = abs(entry - sl) + 1e-9
    rr1  = abs(tp1 - entry) / risk

    return {
        "entry_price":      round(entry, 5),
        "stop_loss":        round(sl, 5),
        "take_profit_1":    round(tp1, 5),
        "take_profit_2":    round(tp2, 5),
        "risk_reward_ratio": round(rr1, 2),
    }


# ── Main Inference Function ───────────────────────────────────────────────────

def run_forecast(
    df_raw: pd.DataFrame,
    symbol: str,
    market_type: str,
    timeframe: str,
    live_price: float,
    price_source: str,
    exchange: str = "binance",
    news_sentiment: float = 0.0,
    is_high_impact_news_window: bool = False,
) -> Dict:
    """
    Full inference pipeline:
      1. Feature engineering
      2. Load or note missing model
      3. Confluence scoring
      4. Trade level calculation
      5. Return structured signal dict
    """
    log.info(f"Running forecast for {symbol} {timeframe} | live=${live_price:.4f}")

    df = add_features(df_raw, live_price=live_price)

    # Initialize rule-based strategy (technicals were already calculated inside add_features)
    strategy = TradingRulesStrategy()
    
    feature_cols = get_feature_cols(df)

    if len(df) < 150:
        raise RuntimeError(f"Insufficient data: {len(df)} rows (need ≥150)")

    latest_row = df.iloc[-1]
    rvol = float(df["rvol_14"].iloc[-1])
    atr  = float(df["atr_14"].iloc[-1])
    # Ensure we use rule strategy ATR if available and fallback if needed
    if pd.notna(latest_row.get("atr")):
        atr = float(latest_row["atr"])
        
    regime = int(df["regime"].iloc[-1])

    mdl = load_active_model(symbol, timeframe)
    if mdl is not None and mdl.trained:
        # Crucial: Use the exact features the model was trained on, not the current dynamically generated list
        try:
            for col in mdl.feature_cols:
                if col not in df.columns:
                    df[col] = 0.0
            X = df[mdl.feature_cols].fillna(0).values
        except KeyError as e:
            # If the dataframe is missing required features, fallback to retraining or fail gracefully
            raise RuntimeError(f"Missing required model features. Please retrain the model. Error: {e}")
        
        win_prob = mdl.predict_proba(X[[-1]])
        model_version = mdl.version
    else:
        # No model trained yet — use confluence scoring only
        log.warning(f"No trained model for {symbol} {timeframe}. Using confluence only.")
        win_prob = None
        model_version = "confluence_only"

    # Confluence scoring
    direction, conf_score, smc_signals = calculate_confluence_score(latest_row)
    trade_levels = calculate_trade_levels(latest_row, direction, live_price, atr)

    # Map direction to signal
    signal_map = {
        "STRONG_LONG": "BUY",  "LONG": "BUY",
        "STRONG_SHORT": "SELL", "SHORT": "SELL",
        "NEUTRAL": "HOLD",
    }
    ml_confluence_signal = signal_map.get(direction, "NO_SIGNAL")

    # Rule-based evaluation
    rule_eval = strategy.evaluate_signals(df, news_sentiment, is_high_impact_news_window)
    rule_signal = rule_eval["signal"]

    # Final Decision logic (combine ML and Rule-based)
    # E.g., if ML and Rules both say BUY, then BUY. If they conflict, HOLD.
    if ml_confluence_signal == rule_signal:
        final_signal = ml_confluence_signal
    elif ml_confluence_signal == "BUY" and rule_signal == "BUY":
        final_signal = "BUY"
    elif ml_confluence_signal == "SELL" and rule_signal == "SELL":
        final_signal = "SELL"
    elif rule_signal != "HOLD" and ml_confluence_signal == "NO_SIGNAL":
        final_signal = rule_signal
    else:
        final_signal = "HOLD"

    # Use model probability if available, otherwise conf_score
    if win_prob is not None:
        confidence_score = float(win_prob)
        bull_prob_pct    = round(win_prob * 100, 1)
    else:
        confidence_score = conf_score / 100.0
        bull_prob_pct    = float(conf_score) if ml_confluence_signal == "BUY" else float(100 - conf_score)

    pred_ret   = (bull_prob_pct / 100 - 0.5) * rvol * 2 if rvol > 0 else 0.0
    pred_price = round(live_price * (1 + pred_ret), 5)
    spread     = rvol * live_price * 0.5
    conf_label = "HIGH" if confidence_score >= 0.65 else "MEDIUM" if confidence_score >= 0.45 else "LOW"

    smc_ctx = {
        "liquidity_sweep": bool(latest_row.get("liquidity_sweep", 0)),
        "bos":             bool(latest_row.get("bullish_bos", 0) or latest_row.get("bearish_bos", 0)),
        "choch":           bool(latest_row.get("choch_signal", 0)),
        "order_block":     bool(latest_row.get("ob_signal", 0)),
        "fvg":             bool(latest_row.get("bullish_fvg", 0) or latest_row.get("bearish_fvg", 0)),
        "displacement":    bool(latest_row.get("displacement", 0)),
        "market_structure": "BULLISH" if latest_row.get("ema_alignment", 0) > 0 else "BEARISH",
        "regime":          "TRENDING" if regime == 1 else "RANGING",
        "session":         str(latest_row.get("session", "NONE")),
        "trend":           "BULLISH" if latest_row.get("ema_alignment", 0) > 0 else "BEARISH",
        "volatility":      "HIGH" if rvol > 0.025 else "MEDIUM" if rvol > 0.012 else "LOW",
        "active_signals":  smc_signals[:8],
    }

    return {
        "symbol":               symbol,
        "market_type":          market_type,
        "timeframe":            timeframe,
        "data_source":          price_source,
        "ml_signal":            ml_confluence_signal,
        "rule_signal":          rule_signal,
        "final_signal":         final_signal,
        "trend_direction":      direction,
        "confidence":           conf_label,
        "confidence_score":     round(confidence_score, 3),
        "confluence_score":     conf_score,
        "current_price":        live_price,
        "predicted_price":      pred_price,
        "predicted_return_pct": round(pred_ret * 100, 3),
        "price_range_low":      round(live_price - spread, 5),
        "price_range_high":     round(live_price + spread, 5),
        "levels":               trade_levels,
        "smc":                  smc_ctx,
        "signal_timestamp":     datetime.now(timezone.utc).isoformat(),
        "model_version":        model_version,
        "rvol":                 round(rvol, 6),
        "atr":                  round(atr, 5),
        "disclaimer": (
            "This signal is a model-generated estimate and is NOT financial advice. "
            "Past performance does not guarantee future results."
        ),
    }
