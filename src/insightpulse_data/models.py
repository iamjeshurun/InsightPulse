"""Domain models and validation for customer feedback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

SOURCES = {"review", "survey", "support_ticket"}
SENTIMENTS = {"positive", "neutral", "negative"}
INTENTS = {"praise", "complaint", "feature_request", "churn_risk", "other"}
URGENCIES = {"low", "medium", "high"}


@dataclass(frozen=True)
class FeedbackRecord:
    id: str
    text: str
    source: str
    product: str
    created_at: str
    sentiment: str | None = None
    intent: str | None = None
    urgency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_label(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    return value or None


def parse_record(raw: dict[str, Any]) -> tuple[FeedbackRecord | None, list[str]]:
    """Validate and normalize one untrusted input record."""
    errors: list[str] = []
    record_id = str(raw.get("id", "")).strip()
    text = " ".join(str(raw.get("text", "")).split())
    source = str(raw.get("source", "")).strip().lower()
    product = " ".join(str(raw.get("product", "")).split())
    created_at = str(raw.get("created_at", "")).strip()
    sentiment = _optional_label(raw.get("sentiment"))
    intent = _optional_label(raw.get("intent"))
    urgency = _optional_label(raw.get("urgency"))

    if not record_id:
        errors.append("id is required")
    if not 3 <= len(text) <= 10_000:
        errors.append("text must contain between 3 and 10,000 characters")
    if source not in SOURCES:
        errors.append(f"source must be one of {sorted(SOURCES)}")
    if not product:
        errors.append("product is required")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        errors.append("created_at must be an ISO-8601 date or timestamp")
    if sentiment and sentiment not in SENTIMENTS:
        errors.append(f"sentiment must be one of {sorted(SENTIMENTS)}")
    if intent and intent not in INTENTS:
        errors.append(f"intent must be one of {sorted(INTENTS)}")
    if urgency and urgency not in URGENCIES:
        errors.append(f"urgency must be one of {sorted(URGENCIES)}")

    if errors:
        return None, errors
    return FeedbackRecord(
        id=record_id,
        text=text,
        source=source,
        product=product,
        created_at=created_at,
        sentiment=sentiment,
        intent=intent,
        urgency=urgency,
    ), []
