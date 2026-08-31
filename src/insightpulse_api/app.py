"""FastAPI application factory and versioned routes."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .cache import TTLCache
from .model_service import ModelService
from .repository import Repository
from .schemas import (
    AnalysisResponse, AnalyticsSummary, AnalyzeRequest, BatchAnalysisResponse,
    BatchAnalyzeRequest, FeedbackRequest, FeedbackResponse, HealthResponse, JobResponse,
)
from insightpulse_monitoring.metrics import MetricsRegistry

API_VERSION = "1.0.0"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": datetime.now(UTC).isoformat(), "level": record.levelname, "message": record.getMessage()})


def create_app(database_path: Path | None = None, model_path: Path | None = None) -> FastAPI:
    repository = Repository(database_path or Path(os.getenv("INSIGHTPULSE_DB", "artifacts/insightpulse.db")))
    model = ModelService(model_path)
    summary_cache = TTLCache(5)
    metrics = MetricsRegistry()
    request_windows: dict[str, deque[float]] = defaultdict(deque)
    rate_lock = threading.Lock()
    app = FastAPI(title="InsightPulse API", version=API_VERSION, docs_url="/docs")
    app.state.repository, app.state.model = repository, model
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("INSIGHTPULSE_CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def operational_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client = request.client.host if request.client else "unknown"
        now = monotonic()
        with rate_lock:
            window = request_windows[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= 120:
                return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"}, headers={"X-Request-ID": request_id})
            window.append(now)
        started = monotonic()
        response = await call_next(request)
        metrics.observe_request(request.method, request.url.path, response.status_code, monotonic() - started)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{(monotonic() - started) * 1000:.2f}"
        return response

    def analyze_one(payload: AnalyzeRequest) -> dict:
        primary, shadow = model.predict_with_shadow([payload.text])
        prediction = primary[0]
        metrics.observe_predictions(prediction)
        if shadow:
            metrics.observe_shadow(prediction, shadow[0])
        record = {
            "id": str(uuid.uuid4()), "text": payload.text, "source": payload.source,
            "product": payload.product, "created_at": datetime.now(UTC).isoformat(),
            "model_version": model.version, "predictions": prediction,
        }
        repository.save_analysis(record)
        summary_cache.clear()
        return record

    @app.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> dict:
        return {"status": "ok", "api_version": API_VERSION, "model_version": model.version}

    @app.get("/ready", tags=["operations"])
    def ready() -> dict:
        if not repository.ping():
            raise HTTPException(503, "database unavailable")
        return {"status": "ready", "model_version": model.version}

    @app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
    def prometheus_metrics() -> str:
        return metrics.render()

    @app.post("/api/v1/analyze", response_model=AnalysisResponse, status_code=201, tags=["inference"])
    def analyze(payload: AnalyzeRequest) -> dict:
        return analyze_one(payload)

    @app.post("/api/v1/analyze/batch", response_model=BatchAnalysisResponse, status_code=201, tags=["inference"])
    def analyze_batch(payload: BatchAnalyzeRequest) -> dict:
        return {"analyses": [analyze_one(record) for record in payload.records]}

    def process_job(job_id: str, records: list[AnalyzeRequest]) -> None:
        repository.update_job(job_id, "running", 0)
        try:
            for completed, record in enumerate(records, start=1):
                analyze_one(record)
                repository.update_job(job_id, "running", completed)
            repository.update_job(job_id, "completed", len(records))
        except Exception as exc:  # surfaced through job status, logged by deployment
            repository.update_job(job_id, "failed", 0, str(exc)[:500])

    @app.post("/api/v1/jobs", response_model=JobResponse, status_code=202, tags=["jobs"])
    def create_job(payload: BatchAnalyzeRequest, background: BackgroundTasks) -> dict:
        job = repository.create_job(len(payload.records))
        background.add_task(process_job, job["id"], payload.records)
        return job

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
    def get_job(job_id: str) -> dict:
        job = repository.get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return job

    @app.get("/api/v1/analyses", response_model=list[AnalysisResponse], tags=["analysis"])
    def list_analyses(limit: int = Query(100, ge=1, le=500), product: str | None = None) -> list[dict]:
        return repository.list_analyses(limit, product)

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse, tags=["analysis"])
    def get_analysis(analysis_id: str) -> dict:
        record = repository.get_analysis(analysis_id)
        if not record:
            raise HTTPException(404, "analysis not found")
        return record

    @app.get("/api/v1/analytics/summary", response_model=AnalyticsSummary, tags=["analytics"])
    def analytics() -> dict:
        cached = summary_cache.get()
        if cached is None:
            cached = repository.analytics()
            summary_cache.set(cached)
        return cached

    @app.post("/api/v1/feedback", response_model=FeedbackResponse, status_code=201, tags=["feedback"])
    def feedback(payload: FeedbackRequest) -> dict:
        if not repository.get_analysis(payload.analysis_id):
            raise HTTPException(404, "analysis not found")
        return repository.save_feedback(payload.analysis_id, payload.task, payload.corrected_label, payload.note)

    frontend = Path(os.getenv("INSIGHTPULSE_FRONTEND_DIST", "frontend/dist"))
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="dashboard")

    return app
