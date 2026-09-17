"""
Model Registry API Routes
Lists, inspects, activates, and downloads trained ML model artifacts.
"""
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import joblib

from ...config.settings import MODEL_DIR

log = logging.getLogger("marketflux.routes.models")
router = APIRouter()


def _inspect_model_file(path: Path) -> Dict:
    stat = path.stat()
    created_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    size_kb = round(stat.st_size / 1024, 1)

    parts = path.stem.split("_")
    symbol = parts[0] if len(parts) > 0 else "UNKNOWN"
    timeframe = parts[1] if len(parts) > 1 else "5m"
    version = "_".join(parts[2:]) if len(parts) > 2 else "active"
    is_active = len(parts) <= 2  # e.g. BTCUSDT_5m.joblib

    metrics = {}
    model_type = "Ensemble"

    try:
        loaded = joblib.load(path)
        if hasattr(loaded, "metrics"):
            metrics = loaded.metrics
        if hasattr(loaded, "model_type"):
            model_type = loaded.model_type
        if hasattr(loaded, "version"):
            version = loaded.version
    except Exception as e:
        log.warning(f"Could not load metadata from {path.name}: {e}")

    return {
        "id": path.stem,
        "filename": path.name,
        "symbol": symbol,
        "timeframe": timeframe,
        "version": version,
        "is_active": is_active,
        "size_kb": size_kb,
        "created_at": created_dt,
        "model_type": model_type,
        "metrics": metrics,
    }


@router.get("")
def list_models():
    """List all saved models in the models directory."""
    if not MODEL_DIR.exists():
        return {"models": []}

    models = []
    for f in MODEL_DIR.glob("*.joblib"):
        try:
            models.append(_inspect_model_file(f))
        except Exception as e:
            log.warning(f"Error inspecting {f.name}: {e}")

    # Sort so active models and newest models appear first
    models.sort(key=lambda m: (1 if m["is_active"] else 0, m["created_at"]), reverse=True)
    return {"count": len(models), "models": models}


@router.get("/{model_id}")
def get_model_details(model_id: str):
    """Get metadata for a specific model."""
    path = MODEL_DIR / f"{model_id}.joblib"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")
    return {"model": _inspect_model_file(path)}


@router.post("/{model_id}/activate")
def activate_model(model_id: str):
    """Set this model as the active production model for its pair/timeframe."""
    source_path = MODEL_DIR / f"{model_id}.joblib"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")

    info = _inspect_model_file(source_path)
    symbol = info["symbol"]
    timeframe = info["timeframe"]

    target_path = MODEL_DIR / f"{symbol}_{timeframe}.joblib"

    try:
        # Load and save to ensure atomic valid copy
        model_obj = joblib.load(source_path)
        joblib.dump(model_obj, target_path)
        log.info(f"Model {model_id} activated as {target_path.name}")
        return {
            "message": f"Model {model_id} successfully activated for {symbol} {timeframe}",
            "active_model": _inspect_model_file(target_path),
        }
    except Exception as e:
        log.error(f"Activation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Could not activate model: {e}")


@router.get("/{model_id}/download")
def download_model(model_id: str):
    """Download the binary .joblib model file."""
    path = MODEL_DIR / f"{model_id}.joblib"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete("/{model_id}")
def delete_model(model_id: str):
    """Delete a model file."""
    path = MODEL_DIR / f"{model_id}.joblib"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found.")

    parts = path.stem.split("_")
    if len(parts) <= 2:
        raise HTTPException(status_code=400, detail="Cannot delete an active base model directly.")

    try:
        path.unlink()
        return {"message": f"Model {model_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
