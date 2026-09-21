"""
Training API Routes
Manages starting, monitoring, streaming, pausing, and stopping model training jobs.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...services.training_service import TrainingJobManager

log = logging.getLogger("marketflux.routes.training")
router = APIRouter()
manager = TrainingJobManager()


class TrainingConfigRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="Trading instrument e.g. BTCUSDT, EURUSD")
    timeframe: str = Field(default="5m", description="1m, 5m, 15m, 1h, 4h, 1d")
    model_type: str = Field(default="ensemble", description="ensemble, xgboost, lightgbm, neural_net, random_forest")
    epochs: int = Field(default=50, ge=5, le=500)
    batch_size: int = Field(default=32, ge=8, le=256)
    learning_rate: float = Field(default=0.05, ge=0.0001, le=1.0)
    limit: int = Field(default=1000, ge=200, le=5000)
    train_split: float = Field(default=0.70, ge=0.5, le=0.9)
    val_split: float = Field(default=0.15, ge=0.05, le=0.3)
    test_split: float = Field(default=0.15, ge=0.05, le=0.3)
    risk_pct: float = Field(default=0.005, ge=0.001, le=0.05)
    lookahead: int = Field(default=20, ge=5, le=100)
    random_seed: int = Field(default=42)


@router.post("/start")
def start_training(req: TrainingConfigRequest):
    """
    Start a real background training job.
    Returns the created job ID and initial state.
    """
    try:
        job = manager.create_job(req.model_dump())
        manager.start_job(job.id)
        return {"message": "Training job started", "job": job.to_dict()}
    except Exception as e:
        log.error(f"Failed to start training: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
def list_jobs():
    """List all training jobs (historical and active)."""
    return {"jobs": manager.list_jobs()}


@router.get("/active")
def get_active_job():
    """Return currently active or running training job, or null."""
    job = manager.get_active_job()
    if not job:
        # If none currently running, return the most recent job so UI can display latest completed state
        all_jobs = manager.list_jobs()
        return {"job": all_jobs[0] if all_jobs else None}
    return {"job": job.to_dict()}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Get full state for a specific job."""
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {"job": job.to_dict()}


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """
    Server-Sent Events (SSE) stream for live training metrics and logs.
    Browser EventSource connects directly to this endpoint.
    """
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    return StreamingResponse(
        manager.stream_job_updates(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/jobs/{job_id}/pause")
def pause_job(job_id: str):
    """Pause an actively running training job."""
    try:
        job = manager.pause_job(job_id)
        return {"message": "Job paused", "job": job.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str):
    """Resume a paused training job."""
    try:
        job = manager.resume_job(job_id)
        return {"message": "Job resumed", "job": job.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str):
    """Gracefully cancel a training job."""
    try:
        job = manager.stop_job(job_id)
        return {"message": "Job stopped", "job": job.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
