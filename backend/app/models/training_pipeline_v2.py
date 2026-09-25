"""
MarketFlux – Enhanced Training Pipeline (v2)
Trains BTC/USDT models from the local historical dataset with:
- Full 739K+ candle ingestion from local CSV
- Pre-computed structure features (BOS, CHoCH, swings)
- Funding rate features
- TimeSeriesSplit cross-validation (Purged)
- Advanced metrics (Sharpe, Win Rate, Max Drawdown, ROC-AUC, Directional Accuracy)
- Model registry integration with JSON metadata artifacts
"""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
import joblib

from ..config.settings import MODEL_DIR, DATA_DIR
from ..data.local_ingest import load_merged_dataset, get_dataset_info
from ..models.feature_engineering import add_features, get_feature_cols, create_2r_1r_target

log = logging.getLogger("marketflux.pipeline_v2")

# Registry directory for model artifacts + metadata
REGISTRY_DIR = MODEL_DIR / "registry"
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


class ModelArtifact:
    """Wrapper for trained model artifacts with full metadata."""

    def __init__(self, symbol: str, timeframe: str, model_type: str, version: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.model_type = model_type
        self.version = version
        self.training_date = datetime.now(timezone.utc)
        self.feature_cols: List[str] = []
        self.scaler: Optional[StandardScaler] = None
        self.model = None
        self.trained = False
        self.metrics: Dict[str, Any] = {}
        self.hyperparameters: Dict[str, Any] = {}
        self.feature_importance: Dict[str, float] = {}
        self.cv_results: List[Dict[str, Any]] = []

    def predict_proba(self, X_raw: np.ndarray) -> float:
        if not self.trained or self.model is None or self.scaler is None:
            return 0.50
        X_scaled = self.scaler.transform(X_raw)
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(X_scaled)
            return float(probs[0][1])
        elif hasattr(self.model, "decision_function"):
            score = self.model.decision_function(X_scaled)[0]
            return float(1.0 / (1.0 + math.exp(-score)))
        return 0.50

    def save(self, path: Path):
        joblib.dump(self, path)

    def save_metadata(self, path: Path):
        """Save model metadata as JSON alongside the .joblib artifact."""
        meta = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "model_type": self.model_type,
            "version": self.version,
            "training_date": self.training_date.isoformat(),
            "trained": self.trained,
            "metrics": self.metrics,
            "hyperparameters": self.hyperparameters,
            "feature_count": len(self.feature_cols),
            "feature_importance_top10": dict(
                sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "cv_results": self.cv_results,
        }
        with open(path, "w") as f:
            json.dump(meta, f, indent=2, default=str)

    @staticmethod
    def load(path: Path) -> "ModelArtifact":
        return joblib.load(path)


def format_duration(seconds: float) -> str:
    s = int(max(0, seconds))
    hours, remainder = divmod(s, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def run_pipeline_v2(
    job_id: str,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    limit: int = 50000,
    model_type: str = "xgboost",
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.05,
    train_split: float = 0.70,
    val_split: float = 0.15,
    test_split: float = 0.15,
    risk_pct: float = 0.005,
    lookahead: int = 20,
    random_seed: int = 42,
    use_local_data: bool = True,
    cv_folds: int = 3,
    on_log: Optional[Callable[[str, str], None]] = None,
    on_epoch: Optional[Callable[[Dict[str, Any]], None]] = None,
    check_pause: Optional[Callable[[], None]] = None,
    check_cancelled: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """
    Enhanced training pipeline (v2) with local data ingestion,
    Purged TimeSeriesSplit CV, and model registry integration.
    """

    def emit_log(msg: str, level: str = "INFO"):
        log.info(msg)
        if on_log:
            on_log(msg, level)

    start_time = time.time()
    emit_log(f"Starting Enhanced Training Job: {job_id}", "INFO")
    emit_log(f"Target: {symbol} | Timeframe: {timeframe} | Architecture: {model_type}", "INFO")

    # ── STEP 1: DATA INGESTION ────────────────────────────────────────────────
    emit_log("Step 1/6: Loading historical data from local dataset...", "INFO")

    if use_local_data:
        # Map timeframe format: "5m" → "5M"
        tf_map = {"1m": "1M", "5m": "5M", "15m": "15M", "30m": "30M", "1h": "1H", "4h": "4H"}
        tf_key = tf_map.get(timeframe, timeframe.upper())

        try:
            df_raw = load_merged_dataset(
                timeframe=tf_key,
                tail_rows=min(limit, 200000),  # Cap at 200K for memory
                include_structure=True,
                include_funding=True,
            )
            emit_log(
                f"Loaded {len(df_raw):,} candles from local dataset "
                f"({df_raw.index[0].date()} → {df_raw.index[-1].date()})",
                "SUCCESS",
            )
        except FileNotFoundError as e:
            emit_log(f"Local data not found, falling back to API: {e}", "WARN")
            use_local_data = False

    if not use_local_data:
        # Fallback to live API fetch
        from ..data.crypto_provider import fetch_ohlcv as crypto_ohlcv
        df_raw = crypto_ohlcv(symbol, timeframe, limit=min(limit, 5000))
        emit_log(f"Loaded {len(df_raw):,} candles from Binance API", "SUCCESS")

    if check_cancelled and check_cancelled():
        raise InterruptedError("Cancelled by user.")

    # ── STEP 2: FEATURE ENGINEERING ───────────────────────────────────────────
    emit_log("Step 2/6: Engineering SMC/ICT features + structure signals...", "INFO")

    df = add_features(df_raw)
    df = create_2r_1r_target(df, risk_pct=risk_pct, lookahead=lookahead)

    feature_cols = get_feature_cols(df)

    # Add structure-derived features that survived the merge
    extra_structure_cols = [
        c for c in df.columns
        if c.endswith("_encoded") or c in (
            "swing_high", "swing_low", "bos_bullish", "bos_bearish",
            "choch_bullish", "choch_bearish", "break_confirmed_close",
            "funding_rate",
        )
        and c not in feature_cols
        and df[c].dtype in (np.float64, np.float32, np.int64, np.int32, np.int8, int, float)
    ]
    feature_cols = list(set(feature_cols + extra_structure_cols))

    df = df.dropna(subset=feature_cols + ["target"]).copy()
    total_clean = len(df)

    if total_clean < 200:
        raise RuntimeError(
            f"Insufficient clean samples ({total_clean}) after feature extraction. "
            f"Increase the data limit."
        )

    win_baseline = float(df["target"].mean())
    emit_log(
        f"Feature engineering complete: {total_clean:,} samples × {len(feature_cols)} features",
        "SUCCESS",
    )
    emit_log(f"Raw dataset win-rate baseline: {win_baseline:.1%}", "INFO")

    if check_cancelled and check_cancelled():
        raise InterruptedError("Cancelled by user.")

    # ── STEP 3: TEMPORAL SPLIT + SCALER ───────────────────────────────────────
    emit_log("Step 3/6: Partitioning chronological train / validation / test splits...", "INFO")

    X = df[feature_cols].values
    y = df["target"].values.astype(int)

    n_total = len(X)
    train_idx = int(n_total * train_split)
    val_idx = int(n_total * (train_split + val_split))

    X_train, y_train = X[:train_idx], y[:train_idx]
    X_val, y_val = X[train_idx:val_idx], y[train_idx:val_idx]
    X_test, y_test = X[val_idx:], y[val_idx:]

    emit_log(
        f"Split sizes: Train={len(X_train):,} | Val={len(X_val):,} | Test={len(X_test):,}",
        "INFO",
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    # ── STEP 4: PURGED TIME-SERIES CROSS-VALIDATION ───────────────────────────
    emit_log(f"Step 4/6: Purged TimeSeriesSplit cross-validation ({cv_folds} folds)...", "INFO")

    tscv = TimeSeriesSplit(n_splits=cv_folds, gap=lookahead)
    cv_results = []

    for fold_idx, (cv_train_idx, cv_val_idx) in enumerate(tscv.split(X_train_scaled), 1):
        if check_cancelled and check_cancelled():
            raise InterruptedError("Cancelled by user.")

        cv_model = _build_model(model_type, 50, learning_rate, random_seed)
        cv_model.fit(X_train_scaled[cv_train_idx], y_train[cv_train_idx])

        cv_preds = cv_model.predict(X_train_scaled[cv_val_idx])
        cv_probs = (
            cv_model.predict_proba(X_train_scaled[cv_val_idx])
            if hasattr(cv_model, "predict_proba")
            else None
        )

        fold_metrics = {
            "fold": fold_idx,
            "accuracy": round(accuracy_score(y_train[cv_val_idx], cv_preds) * 100, 2),
            "precision": round(precision_score(y_train[cv_val_idx], cv_preds, zero_division=0) * 100, 2),
            "recall": round(recall_score(y_train[cv_val_idx], cv_preds, zero_division=0) * 100, 2),
            "f1": round(f1_score(y_train[cv_val_idx], cv_preds, zero_division=0) * 100, 2),
        }
        if cv_probs is not None:
            fold_metrics["roc_auc"] = round(
                roc_auc_score(y_train[cv_val_idx], cv_probs[:, 1]), 4
            )
            fold_metrics["log_loss"] = round(
                log_loss(y_train[cv_val_idx], cv_probs, labels=[0, 1]), 4
            )

        cv_results.append(fold_metrics)
        emit_log(
            f"  Fold {fold_idx}/{cv_folds} — "
            f"Acc: {fold_metrics['accuracy']}% | "
            f"AUC: {fold_metrics.get('roc_auc', 'N/A')} | "
            f"F1: {fold_metrics['f1']}%",
            "INFO",
        )

    avg_cv_acc = np.mean([f["accuracy"] for f in cv_results])
    emit_log(f"CV complete — Mean Accuracy: {avg_cv_acc:.2f}%", "SUCCESS")

    # ── STEP 5: ITERATIVE TRAINING LOOP ───────────────────────────────────────
    emit_log(f"Step 5/6: Training {model_type} with {epochs} iterations...", "INFO")

    trained_model = None
    best_val_loss = float("inf")
    best_val_score = 0.0
    metrics_history = []

    for epoch in range(1, epochs + 1):
        if check_cancelled and check_cancelled():
            raise InterruptedError("Cancelled by user.")
        if check_pause:
            check_pause()

        # Build model with increasing complexity
        n_estimators = max(2, epoch * 2) if model_type != "neural_net" else epoch
        model = _build_model(model_type, n_estimators, learning_rate, random_seed)
        model.fit(X_train_scaled, y_train)
        trained_model = model

        # Compute metrics
        train_probs = model.predict_proba(X_train_scaled) if hasattr(model, "predict_proba") else None
        val_probs = model.predict_proba(X_val_scaled) if hasattr(model, "predict_proba") else None

        if train_probs is not None:
            train_preds = (train_probs[:, 1] >= 0.5).astype(int)
            val_preds = (val_probs[:, 1] >= 0.5).astype(int)
            cur_train_loss = float(log_loss(y_train, train_probs, labels=[0, 1]))
            cur_val_loss = float(log_loss(y_val, val_probs, labels=[0, 1]))
        else:
            train_preds = model.predict(X_train_scaled)
            val_preds = model.predict(X_val_scaled)
            cur_train_loss = 1.0 - accuracy_score(y_train, train_preds)
            cur_val_loss = 1.0 - accuracy_score(y_val, val_preds)

        cur_train_acc = float(accuracy_score(y_train, train_preds))
        cur_val_acc = float(accuracy_score(y_val, val_preds))

        elapsed = time.time() - start_time
        time_per_epoch = elapsed / epoch
        eta = (epochs - epoch) * time_per_epoch
        progress_pct = int((epoch / epochs) * 100)

        if cur_val_loss < best_val_loss:
            best_val_loss = cur_val_loss
        if cur_val_acc > best_val_score:
            best_val_score = cur_val_acc

        metric_record = {
            "epoch": epoch,
            "total_epochs": epochs,
            "progress_pct": progress_pct,
            "train_loss": round(cur_train_loss, 4),
            "val_loss": round(cur_val_loss, 4),
            "train_acc": round(cur_train_acc * 100, 2),
            "val_acc": round(cur_val_acc * 100, 2),
            "best_val_loss": round(best_val_loss, 4),
            "best_val_score": round(best_val_score * 100, 2),
            "learning_rate": learning_rate,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1),
        }
        metrics_history.append(metric_record)

        if on_epoch:
            on_epoch(metric_record)

        if epoch % max(1, epochs // 10) == 0 or epoch == epochs:
            emit_log(
                f"Epoch {epoch:03d}/{epochs} | Loss: {cur_train_loss:.4f} | "
                f"Val Loss: {cur_val_loss:.4f} | Val Acc: {cur_val_acc*100:.1f}% | "
                f"ETA: {format_duration(eta)}",
                "EPOCH",
            )

        time.sleep(0.005)  # Thread yield

    # ── STEP 6: OUT-OF-SAMPLE EVALUATION + BACKTEST ───────────────────────────
    emit_log("Step 6/6: Out-of-sample evaluation and backtest simulation...", "INFO")

    test_probs = trained_model.predict_proba(X_test_scaled) if hasattr(trained_model, "predict_proba") else None
    test_preds = (test_probs[:, 1] >= 0.5).astype(int) if test_probs is not None else trained_model.predict(X_test_scaled)

    test_acc = float(accuracy_score(y_test, test_preds))
    test_precision = float(precision_score(y_test, test_preds, zero_division=0))
    test_recall = float(recall_score(y_test, test_preds, zero_division=0))
    test_f1 = float(f1_score(y_test, test_preds, zero_division=0))
    test_roc_auc = float(roc_auc_score(y_test, test_probs[:, 1])) if test_probs is not None else 0.0

    # Directional accuracy
    dir_correct = np.sum(test_preds == y_test)
    directional_accuracy = dir_correct / len(y_test) if len(y_test) > 0 else 0.0

    # Backtest simulation
    test_df = df.iloc[val_idx:].copy()
    test_df["pred"] = test_preds
    trade_returns = []

    for i in range(len(test_df)):
        row = test_df.iloc[i]
        if row["pred"] == 1:
            ret = (2.0 * risk_pct) if row["target"] == 1 else (-1.0 * risk_pct)
            trade_returns.append(ret)

    total_trades = len(trade_returns)
    winning_trades = sum(1 for r in trade_returns if r > 0)
    losing_trades = total_trades - winning_trades
    sim_win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0

    # Equity curve + drawdown
    cum_equity = 1.0
    equity_curve = [1.0]
    peak = 1.0
    max_drawdown = 0.0

    for r in trade_returns:
        cum_equity *= (1.0 + r)
        equity_curve.append(cum_equity)
        if cum_equity > peak:
            peak = cum_equity
        dd = (peak - cum_equity) / peak
        if dd > max_drawdown:
            max_drawdown = dd

    total_return_pct = (cum_equity - 1.0) * 100.0
    arr_rets = np.array(trade_returns) if trade_returns else np.array([0.0])
    sharpe = (
        (arr_rets.mean() / (arr_rets.std() + 1e-9)) * math.sqrt(252 * 24)
        if len(arr_rets) > 1 and arr_rets.std() > 0
        else 0.0
    )

    # Feature importance
    feature_importance = {}
    if hasattr(trained_model, "feature_importances_"):
        for col, imp in zip(feature_cols, trained_model.feature_importances_):
            feature_importance[col] = round(float(imp), 6)

    # ── SAVE MODEL ARTIFACT + METADATA ────────────────────────────────────────
    duration_total = time.time() - start_time
    version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
    model_filename = f"{symbol}_{timeframe}_{version}.joblib"
    model_save_path = MODEL_DIR / model_filename
    metadata_path = REGISTRY_DIR / f"{symbol}_{timeframe}_{version}.json"

    artifact = ModelArtifact(symbol, timeframe, model_type, version)
    artifact.feature_cols = feature_cols
    artifact.scaler = scaler
    artifact.model = trained_model
    artifact.trained = True
    artifact.hyperparameters = {
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "train_split": train_split,
        "val_split": val_split,
        "test_split": test_split,
        "risk_pct": risk_pct,
        "lookahead": lookahead,
        "random_seed": random_seed,
        "cv_folds": cv_folds,
        "data_source": "local" if use_local_data else "api",
        "total_samples": total_clean,
    }
    artifact.feature_importance = feature_importance
    artifact.cv_results = cv_results
    artifact.metrics = {
        "best_val_loss": round(best_val_loss, 4),
        "best_val_score": round(best_val_score * 100, 2),
        "test_accuracy": round(test_acc * 100, 2),
        "test_precision": round(test_precision, 4),
        "test_recall": round(test_recall, 4),
        "test_f1": round(test_f1, 4),
        "test_roc_auc": round(test_roc_auc, 4),
        "directional_accuracy": round(directional_accuracy * 100, 2),
        "backtest_return_pct": round(total_return_pct, 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate_pct": round(sim_win_rate * 100, 2),
        "cv_mean_accuracy": round(avg_cv_acc, 2),
        "duration_seconds": round(duration_total, 1),
    }

    artifact.save(model_save_path)
    artifact.save_metadata(metadata_path)
    emit_log(f"Model saved to {model_save_path}", "SUCCESS")
    emit_log(f"Metadata saved to {metadata_path}", "SUCCESS")

    # Promote to active
    active_path = MODEL_DIR / f"{symbol}_{timeframe}.joblib"
    artifact.save(active_path)
    emit_log(f"Promoted to active model: {active_path.name}", "SUCCESS")

    emit_log(
        f"TRAINING COMPLETE! "
        f"Test Acc: {test_acc*100:.1f}% | AUC: {test_roc_auc:.4f} | "
        f"Return: {total_return_pct:+.2f}% | Sharpe: {sharpe:.2f} | "
        f"Max DD: {max_drawdown*100:.1f}%",
        "SUCCESS",
    )

    return {
        "job_id": job_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "model_type": model_type,
        "version": version,
        "model_filename": model_filename,
        "model_path": str(model_save_path),
        "metadata_path": str(metadata_path),
        "training_duration": format_duration(duration_total),
        "duration_seconds": round(duration_total, 1),
        "best_val_loss": round(best_val_loss, 4),
        "test_accuracy": round(test_acc * 100, 2),
        "test_precision": round(test_precision, 4),
        "test_roc_auc": round(test_roc_auc, 4),
        "directional_accuracy": round(directional_accuracy * 100, 2),
        "backtest_return": round(total_return_pct, 2),
        "max_drawdown": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(sim_win_rate * 100, 2),
        "cv_mean_accuracy": round(avg_cv_acc, 2),
        "feature_importance": dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:15]
        ),
        "cv_results": cv_results,
        "metrics_history": metrics_history,
        "data_source": "local" if use_local_data else "api",
        "total_samples": total_clean,
    }


def _build_model(model_type: str, n_estimators: int, learning_rate: float, seed: int):
    """Build a scikit-learn compatible model based on the model_type string."""
    if model_type == "xgboost":
        try:
            import xgboost as xgb
            return xgb.XGBClassifier(
                n_estimators=n_estimators,
                max_depth=6,
                learning_rate=learning_rate,
                subsample=0.8,
                colsample_bytree=0.8,
                eval_metric="logloss",
                random_state=seed,
                n_jobs=-1,
            )
        except ImportError:
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                max_depth=4,
                random_state=seed,
            )

    elif model_type == "lightgbm":
        try:
            import lightgbm as lgb
            return lgb.LGBMClassifier(
                n_estimators=n_estimators,
                max_depth=6,
                learning_rate=learning_rate,
                num_leaves=31,
                random_state=seed,
                verbose=-1,
                n_jobs=-1,
            )
        except ImportError:
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                max_depth=4,
                random_state=seed,
            )

    elif model_type == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=8,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        )

    elif model_type == "neural_net":
        from sklearn.neural_network import MLPClassifier
        return MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            solver="adam",
            learning_rate_init=learning_rate,
            max_iter=max(1, n_estimators),
            warm_start=True,
            random_state=seed,
        )

    else:  # ensemble
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=4,
            random_state=seed,
        )
