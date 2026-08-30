"""Versioned API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=3, max_length=10_000)
    source: Literal["review", "survey", "support_ticket"] = "review"
    product: str = Field(default="Unknown", min_length=1, max_length=200)


class BatchAnalyzeRequest(BaseModel):
    records: list[AnalyzeRequest] = Field(min_length=1, max_length=100)


class TaskPrediction(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    probabilities: dict[str, float]


class AnalysisResponse(BaseModel):
    id: str
    text: str
    source: str
    product: str
    created_at: datetime
    model_version: str
    predictions: dict[str, TaskPrediction]


class BatchAnalysisResponse(BaseModel):
    analyses: list[AnalysisResponse]


class JobResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    total: int
    completed: int
    error: str | None = None


class FeedbackRequest(BaseModel):
    analysis_id: str
    task: Literal["sentiment", "intent", "urgency"]
    corrected_label: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1_000)


class FeedbackResponse(BaseModel):
    id: str
    created_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok"]
    api_version: str
    model_version: str


class AnalyticsSummary(BaseModel):
    total: int
    average_confidence: float
    sentiment: dict[str, int]
    intent: dict[str, int]
    urgency: dict[str, int]
    products: dict[str, int]
    by_day: dict[str, int]
    low_confidence: int
