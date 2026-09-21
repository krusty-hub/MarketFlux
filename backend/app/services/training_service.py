"""
MarketFlux – Training Job Manager Service
Manages real asynchronous model training jobs, background thread workers,
persistent state across server and browser reloads, and Server-Sent Events (SSE) streaming.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..config.settings import DATA_DIR
from ..models.training_pipeline import run_pipeline, format_duration

log = logging.getLogger("marketflux.training_service")
JOBS_FILE = DATA_DIR / "training_jobs.json"


class TrainingJob:
    def __init__(self, job_id: str, config: Dict[str, Any]):
        self.id = job_id
        self.symbol = config.get("symbol", "BTCUSDT")
        self.timeframe = config.get("timeframe", "5m")
        self.model_type = config.get("model_type", "ensemble")
        self.epochs = int(config.get("epochs", 50))
        self.batch_size = int(config.get("batch_size", 32))
        self.learning_rate = float(config.get("learning_rate", 0.05))
        self.limit = int(config.get("limit", 1000))
        self.train_split = float(config.get("train_split", 0.70))
        self.val_split = float(config.get("val_split", 0.15))
        self.test_split = float(config.get("test_split", 0.15))
        self.risk_pct = float(config.get("risk_pct", 0.005))
        self.lookahead = int(config.get("lookahead", 20))
        self.random_seed = int(config.get("random_seed", 42))

        # Runtime State: IDLE | QUEUED | STARTING | RUNNING | PAUSED | COMPLETED | FAILED | CANCELLED
        self.status = "QUEUED"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

        # Metrics
        self.current_epoch = 0
        self.progress_pct = 0
        self.train_loss: Optional[float] = None
        self.val_loss: Optional[float] = None
        self.train_acc: Optional[float] = None
        self.val_acc: Optional[float] = None
        self.best_val_loss: Optional[float] = None
        self.best_val_score: Optional[float] = None
        self.elapsed_seconds = 0.0
        self.eta_seconds = 0.0
        self.model_path: Optional[str] = None
        self.model_version: Optional[str] = None
        self.error: Optional[str] = None

        # Logs and charts
        self.logs: List[Dict[str, str]] = []
        self.metrics_history: List[Dict[str, Any]] = []
        self.summary: Optional[Dict[str, Any]] = None

        # Flow control
        self._pause_event = threading.Event()
        self._pause_event.set()  # set means running, clear means paused
        self._cancel_flag = False
        self._thread: Optional[threading.Thread] = None

        # SSE Listeners (async queues)
        self._subscribers: List[asyncio.Queue] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "model_type": self.model_type,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "limit": self.limit,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "current_epoch": self.current_epoch,
            "progress_pct": self.progress_pct,
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            "train_acc": self.train_acc,
            "val_acc": self.val_acc,
            "best_val_loss": self.best_val_loss,
            "best_val_score": self.best_val_score,
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_formatted": format_duration(self.elapsed_seconds),
            "eta_seconds": self.eta_seconds,
            "eta_formatted": format_duration(self.eta_seconds),
            "model_path": self.model_path,
            "model_version": self.model_version,
            "error": self.error,
            "logs_count": len(self.logs),
            "recent_logs": self.logs[-50:],  # Most recent 50 logs for fast previews
            "metrics_history": self.metrics_history,
            "summary": self.summary,
        }

    def add_log(self, text: str, level: str = "INFO"):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {"timestamp": ts, "level": level, "text": text}
        self.logs.append(entry)
        self._broadcast({"type": "log", "data": entry})

    def update_metrics(self, data: Dict[str, Any]):
        self.current_epoch = data.get("epoch", self.current_epoch)
        self.progress_pct = data.get("progress_pct", self.progress_pct)
        self.train_loss = data.get("train_loss", self.train_loss)
        self.val_loss = data.get("val_loss", self.val_loss)
        self.train_acc = data.get("train_acc", self.train_acc)
        self.val_acc = data.get("val_acc", self.val_acc)
        self.best_val_loss = data.get("best_val_loss", self.best_val_loss)
        self.best_val_score = data.get("best_val_score", self.best_val_score)
        self.elapsed_seconds = data.get("elapsed_seconds", self.elapsed_seconds)
        self.eta_seconds = data.get("eta_seconds", self.eta_seconds)
        self.metrics_history.append(data)
        self._broadcast({"type": "metrics", "data": data})

    def set_status(self, new_status: str, error: Optional[str] = None):
        self.status = new_status
        if error:
            self.error = error
        if new_status in ("COMPLETED", "FAILED", "CANCELLED"):
            self.completed_at = datetime.now(timezone.utc).isoformat()
        self._broadcast({"type": "status", "status": new_status, "error": error})

    def _broadcast(self, msg: Dict[str, Any]):
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except Exception:
                pass


class TrainingJobManager:
    _instance: Optional[TrainingJobManager] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TrainingJobManager, cls).__new__(cls)
                    cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.jobs: Dict[str, TrainingJob] = {}
        self._file_lock = threading.Lock()
        self._load_saved_jobs()

    def _load_saved_jobs(self):
        """Restore previous training jobs metadata from disk."""
        if JOBS_FILE.exists():
            try:
                with open(JOBS_FILE, "r") as f:
                    data = json.load(f)
                    for jdata in data:
                        job = TrainingJob(jdata["id"], jdata)
                        job.status = jdata.get("status", "COMPLETED")
                        job.created_at = jdata.get("created_at")
                        job.started_at = jdata.get("started_at")
                        job.completed_at = jdata.get("completed_at")
                        job.current_epoch = jdata.get("current_epoch", 0)
                        job.progress_pct = jdata.get("progress_pct", 0)
                        job.train_loss = jdata.get("train_loss")
                        job.val_loss = jdata.get("val_loss")
                        job.train_acc = jdata.get("train_acc")
                        job.val_acc = jdata.get("val_acc")
                        job.best_val_loss = jdata.get("best_val_loss")
                        job.best_val_score = jdata.get("best_val_score")
                        job.model_path = jdata.get("model_path")
                        job.model_version = jdata.get("model_version")
                        job.summary = jdata.get("summary")
                        job.metrics_history = jdata.get("metrics_history", [])
                        job.logs = jdata.get("recent_logs", [])
                        self.jobs[job.id] = job
                log.info(f"Loaded {len(self.jobs)} historical training jobs from disk.")
            except Exception as e:
                log.warning(f"Could not load saved jobs: {e}")

    def _save_jobs(self):
        """Persist jobs metadata to disk."""
        with self._file_lock:
            try:
                payload = [job.to_dict() for job in self.jobs.values()]
                with open(JOBS_FILE, "w") as f:
                    json.dump(payload, f, indent=2)
            except Exception as e:
                log.warning(f"Could not persist jobs: {e}")

    def create_job(self, config: Dict[str, Any]) -> TrainingJob:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        count = len(self.jobs) + 1
        job_id = f"train_{timestamp}_{count:03d}"

        job = TrainingJob(job_id, config)
        self.jobs[job_id] = job
        self._save_jobs()
        return job

    def start_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        if job.status == "RUNNING":
            return job

        job.set_status("STARTING")
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.add_log(f"Job {job_id} queued for execution on background worker thread.")

        thread = threading.Thread(target=self._worker_execute, args=(job,), daemon=True)
        job._thread = thread
        thread.start()
        return job

    def pause_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")
        if job.status == "RUNNING":
            job._pause_event.clear()
            job.set_status("PAUSED")
            job.add_log("Training paused by user.", "WARN")
            self._save_jobs()
        return job

    def resume_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")
        if job.status == "PAUSED":
            job._pause_event.set()
            job.set_status("RUNNING")
            job.add_log("Training resumed.", "INFO")
            self._save_jobs()
        return job

    def stop_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")
        job._cancel_flag = True
        job._pause_event.set()  # unblock if paused so thread can exit
        job.set_status("CANCELLED")
        job.add_log("Training cancelled by user.", "WARN")
        self._save_jobs()
        return job

    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        # Sort latest first
        sorted_jobs = sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in sorted_jobs]

    def get_active_job(self) -> Optional[TrainingJob]:
        for job in self.jobs.values():
            if job.status in ("STARTING", "RUNNING", "PAUSED"):
                return job
        return None

    def _worker_execute(self, job: TrainingJob):
        """Worker thread executing the real Python ML training pipeline."""
        try:
            job.set_status("RUNNING")
            self._save_jobs()

            def _check_pause():
                job._pause_event.wait()

            def _check_cancelled():
                return job._cancel_flag

            summary = run_pipeline(
                job_id=job.id,
                symbol=job.symbol,
                timeframe=job.timeframe,
                limit=job.limit,
                model_type=job.model_type,
                epochs=job.epochs,
                batch_size=job.batch_size,
                learning_rate=job.learning_rate,
                train_split=job.train_split,
                val_split=job.val_split,
                test_split=job.test_split,
                risk_pct=job.risk_pct,
                lookahead=job.lookahead,
                random_seed=job.random_seed,
                on_log=job.add_log,
                on_epoch=job.update_metrics,
                check_pause=_check_pause,
                check_cancelled=_check_cancelled,
            )

            job.summary = summary
            job.model_path = summary.get("model_path")
            job.model_version = summary.get("version")
            job.progress_pct = 100
            job.set_status("COMPLETED")
            job.add_log("Training session finalized and serialized successfully.", "SUCCESS")

        except InterruptedError:
            job.set_status("CANCELLED")
            job.add_log("Training cleanly halted.", "WARN")
        except Exception as e:
            log.error(f"Training job {job.id} failed: {e}", exc_info=True)
            job.set_status("FAILED", error=str(e))
            job.add_log(f"Fatal error during training: {e}", "ERROR")
        finally:
            self._save_jobs()

    async def stream_job_updates(self, job_id: str) -> AsyncGenerator[str, None]:
        """SSE Generator yielding event-stream chunks for real-time frontend updates."""
        job = self.get_job(job_id)
        if not job:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        queue: asyncio.Queue = asyncio.Queue()
        job._subscribers.append(queue)

        # First send full current snapshot
        snapshot = {"type": "snapshot", "data": job.to_dict()}
        yield f"data: {json.dumps(snapshot)}\n\n"

        try:
            while True:
                # Wait for next event or heartbeat
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("type") == "status" and msg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                        # Send one final snapshot and close
                        final_snap = {"type": "snapshot", "data": job.to_dict()}
                        yield f"data: {json.dumps(final_snap)}\n\n"
                        break
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep SSE connection alive
                    yield ": ping\n\n"
                    if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
                        break
        finally:
            if queue in job._subscribers:
                job._subscribers.remove(queue)
