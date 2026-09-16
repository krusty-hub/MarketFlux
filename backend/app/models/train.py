"""
MarketFlux – Local Model Training Script
Run this to generate the training dataset and train/save the ML model.

Usage:
    python -m backend.app.models.train --symbol BTCUSDT --interval 5m --limit 1000

Steps:
  1. Download Binance historical klines
  2. Calculate SMC/ICT features
  3. Generate 2R/1R binary target labels
  4. Train ensemble (RF + XGBoost + LightGBM)
  5. Evaluate on out-of-sample split
  6. Save model if it beats the currently active model
  7. Log model version to Supabase (optional)
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import os
os.environ["PYTHONWARNINGS"] = "ignore"

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    precision_score,
    accuracy_score,
    recall_score,
    f1_score,
)

# Allow running as a module or directly
sys.path.insert(0, str(Path(__file__).parents[4]))

from backend.app.data.crypto_provider import fetch_ohlcv
from backend.app.models.feature_engineering import (
    add_features,
    get_feature_cols,
    create_2r_1r_target,
)
from backend.app.models.forecasting_engine import (
    InstitutionalForecastModel,
    load_active_model,
)
from backend.app.config.settings import MODEL_DIR, DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("marketflux.train")


def run_training(
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    limit: int = 1000,
    risk_pct: float = 0.005,
    lookahead: int = 20,
    test_size: float = 0.2,
    log_to_supabase: bool = False,
) -> InstitutionalForecastModel:
    """
    Full training pipeline. Returns the trained model.
    Only saves and promotes if it beats the active model.
    """
    log.info("═══ MarketFlux Training Pipeline ═══")
    log.info(f"Symbol: {symbol} | Timeframe: {timeframe} | Limit: {limit}")

    # ── Step 1: Fetch historical OHLCV ───────────────────────────────────────
    log.info("Step 1: Fetching historical OHLCV …")
    df_raw = fetch_ohlcv(symbol, timeframe, limit)
    log.info(f"  Downloaded {len(df_raw)} candles for {symbol} {timeframe}")

    # Save raw data cache
    cache_path = DATA_DIR / f"{symbol}_{timeframe}_raw.parquet"
    df_raw.to_parquet(cache_path)
    log.info(f"  Raw data cached → {cache_path}")

    # ── Step 2: Feature Engineering ───────────────────────────────────────────
    log.info("Step 2: Engineering SMC/ICT features …")
    df = add_features(df_raw)
    df = create_2r_1r_target(df, risk_pct=risk_pct, lookahead=lookahead)

    # Drop rows with NaN in features or target
    feature_cols = get_feature_cols(df)
    df = df.dropna(subset=feature_cols + ["target"])
    log.info(f"  Clean dataset: {len(df)} rows × {len(feature_cols)} features")
    log.info(f"  Win rate in training data: {df['target'].mean():.1%}")

    if len(df) < 200:
        raise RuntimeError(f"Not enough clean data after feature engineering ({len(df)} rows). "
                           "Increase --limit.")

    # ── Step 3: Train / Test Split (Stratified) ──────────────────
    log.info("Step 3: Splitting train / test (stratified) …")
    X = df[feature_cols]  # Pass as DataFrame, NOT .values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=42
    )
    log.info(f"  Train: {len(X_train)} | Test (OOS): {len(X_test)}")

    # ── Step 4: Train new model ───────────────────────────────────────────────
    log.info("Step 4: Training ensemble …")
    new_model = InstitutionalForecastModel(symbol, timeframe)
    new_model.fit(X_train, y_train, feature_cols)

    # ── Step 5: Evaluate on OOS test set ─────────────────────────────────────
    log.info("Step 5: Evaluating on out-of-sample test set …")
    # Convert probabilities to binary predictions
    new_preds  = (np.array([new_model.predict_proba(X_test.iloc[[i]]) for i in range(len(X_test))]) >= 0.5).astype(int)

    new_win_rate = float(accuracy_score(y_test, new_preds))
    new_precision = float(precision_score(y_test, new_preds, zero_division=0))
    new_recall = float(recall_score(y_test, new_preds, zero_division=0))
    new_f1 = float(f1_score(y_test, new_preds, zero_division=0))

    log.info(f"\n{classification_report(y_test, new_preds, labels=[0, 1], target_names=['LOSS', 'WIN'], zero_division=0)}")
    log.info(f"  New model (Class 1) -> Precision: {new_precision:.3f} | Recall: {new_recall:.3f} | F1-Score: {new_f1:.3f}")

    # ── Step 6: Compare with active model ────────────────────────────────────
    log.info("Step 6: Comparing with active model …")
    active = load_active_model(symbol, timeframe)
    should_promote = True

    if active is not None and active.trained:
        old_preds = (np.array([active.predict_proba(X_test.iloc[[i]]) for i in range(len(X_test))]) >= 0.5).astype(int)
        old_precision = float(precision_score(y_test, old_preds, zero_division=0))
        old_recall = float(recall_score(y_test, old_preds, zero_division=0))
        old_f1 = float(f1_score(y_test, old_preds, zero_division=0))
        
        log.info(f"  Active model (Class 1) -> Precision: {old_precision:.3f} | Recall: {old_recall:.3f} | F1-Score: {old_f1:.3f}")

        # Promote if F1 and Precision are improved or equal but overall better
        if new_f1 < old_f1 or (new_f1 == old_f1 and new_precision <= old_precision):
            should_promote = False
            log.warning(
                f"  New model (F1: {new_f1:.3f}) does not beat active model (F1: {old_f1:.3f}). "
                "Not promoting."
            )
        else:
            log.info(f"  New model wins (F1: {new_f1:.3f} > {old_f1:.3f}). Promoting.")
    else:
        log.info("  No active model found. Promoting new model automatically.")

    # ── Step 7: Save model ────────────────────────────────────────────────────
    model_path = MODEL_DIR / f"{symbol}_{timeframe}.joblib"
    if should_promote:
        new_model.save(model_path)
        log.info(f"  Model saved → {model_path} (version={new_model.version})")

        # ── Step 8: Log to Supabase (optional) ───────────────────────────────
        if log_to_supabase:
            _log_model_version_to_supabase(
                symbol=symbol,
                timeframe=timeframe,
                model=new_model,
                dataset_size=len(df),
                win_rate=new_win_rate,
                precision=new_precision,
                model_path=str(model_path),
            )
    else:
        log.info("  Active model retained. New model discarded.")

    log.info("═══ Training Complete ═══")
    return new_model


def _log_model_version_to_supabase(
    symbol: str,
    timeframe: str,
    model: InstitutionalForecastModel,
    dataset_size: int,
    win_rate: float,
    precision: float,
    model_path: str,
) -> None:
    """Insert a new record into the model_versions table in Supabase."""
    try:
        from supabase import create_client
        from backend.app.config.settings import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            log.warning("Supabase credentials not set. Skipping model version logging.")
            return

        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

        # Mark all existing versions for this symbol/timeframe as inactive
        client.table("model_versions").update({"is_active": False}).eq(
            "symbol", symbol
        ).eq("timeframe", timeframe).execute()

        # Insert new active version
        client.table("model_versions").insert({
            "version":       model.version,
            "symbol":        symbol,
            "timeframe":     timeframe,
            "training_date": model.training_date.isoformat(),
            "dataset_size":  dataset_size,
            "win_rate":      round(win_rate, 4),
            "profit_factor": 0.0,    # calculated after live trading
            "max_drawdown":  0.0,    # calculated after live trading
            "precision":     round(precision, 4),
            "model_path":    model_path,
            "is_active":     True,
        }).execute()

        log.info(f"  Model version {model.version} logged to Supabase.")

    except Exception as e:
        log.warning(f"Failed to log model version to Supabase: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train MarketFlux ML model")
    parser.add_argument("--symbol",     default="BTCUSDT", help="Symbol e.g. BTCUSDT")
    parser.add_argument("--interval",   default="5m",      help="Timeframe e.g. 5m, 1h")
    parser.add_argument("--limit",      type=int, default=1000, help="Number of candles")
    parser.add_argument("--risk-pct",   type=float, default=0.005, help="Risk %% for 1R target")
    parser.add_argument("--lookahead",  type=int, default=20, help="Candles to check for target")
    parser.add_argument("--supabase",   action="store_true", help="Log model version to Supabase")
    args = parser.parse_args()

    try:
        run_training(
            symbol=args.symbol,
            timeframe=args.interval,
            limit=args.limit,
            risk_pct=args.risk_pct,
            lookahead=args.lookahead,
            log_to_supabase=args.supabase,
        )
    except Exception as exc:
        log.error(f"Training failed: {exc}", exc_info=True)
        sys.exit(1)
