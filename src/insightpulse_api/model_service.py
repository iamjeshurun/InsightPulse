"""Model loading and safe local inference.

Each task is served by its own trained model when one is configured and falls
back to a transparent rule-based lexicon otherwise, so a partial deployment
(say, sentiment only) still returns every field the dashboard expects.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib

from insightpulse_data.cfpb import classify_aspect

TASKS = ("sentiment", "intent", "urgency", "aspect")

POSITIVE = {"excellent", "great", "love", "fast", "helpful", "clear", "wonderful", "solved", "professional"}
NEGATIVE = {"broken", "bad", "hate", "slow", "freeze", "freezes", "charged", "locked", "cancel", "fails", "failed", "outrageous", "unacceptable"}
URGENT = {
    "urgent", "immediately", "asap", "emergency", "outage", "down", "security",
    "breach", "fraud", "fraudulent", "unauthorized", "stolen", "scam", "hacked",
    "charged", "locked", "lawsuit", "legal", "safety",
}
CHURN_PHRASES = (
    "cancel", "leave", "switch provider", "switch to", "switch banks",
    "close my account", "close our account", "close my subscription",
    "take my business", "moving to a competitor", "will not renew", "won't renew",
)

LABELS: dict[str, list[str]] = {
    "sentiment": ["negative", "neutral", "positive"],
    "intent": ["churn_risk", "complaint", "feature_request", "other", "praise"],
    "urgency": ["high", "low", "medium"],
    "aspect": [
        "account_access", "credit_reporting", "debt_collection", "fees_interest",
        "fraud_security", "loan_servicing", "other", "payments",
    ],
}


def _load(raw: str | Path | None) -> Any | None:
    if not raw:
        return None
    path = Path(raw)
    return joblib.load(path) if path.exists() else None


class ModelService:
    def __init__(self, model_path: Path | None = None) -> None:
        primary = _load(model_path or os.getenv("INSIGHTPULSE_MODEL_PATH"))
        primary_tasks = set(getattr(getattr(primary, "config", None), "tasks", ()) or ())

        self._task_models: dict[str, Any] = {}
        stamps: dict[str, str] = {}
        for task in TASKS:
            override = _load(os.getenv(f"INSIGHTPULSE_{task.upper()}_MODEL_PATH"))
            if override is not None:
                self._task_models[task], stamps[task] = override, _stamp(override)
            elif primary is not None and task in primary_tasks:
                self._task_models[task], stamps[task] = primary, _stamp(primary)

        if self._task_models:
            self.version = "+".join(f"{task}:{stamps.get(task, 'lexicon')}" for task in TASKS)
        else:
            self.version = "demo-lexicon-2"

        self.shadow_model = _load(os.getenv("INSIGHTPULSE_SHADOW_MODEL_PATH"))

    @staticmethod
    def _distribution(label: str, labels: list[str], confidence: float) -> dict[str, float]:
        remainder = (1 - confidence) / max(len(labels) - 1, 1)
        return {candidate: confidence if candidate == label else remainder for candidate in labels}

    def _demo_predict(self, text: str) -> dict[str, dict[str, Any]]:
        tokens = set(text.lower().replace(".", " ").replace(",", " ").split())
        positive, negative = len(tokens & POSITIVE), len(tokens & NEGATIVE)
        if positive > negative:
            sentiment, confidence = "positive", min(0.62 + positive * 0.08, 0.9)
        elif negative > positive:
            sentiment, confidence = "negative", min(0.62 + negative * 0.08, 0.9)
        else:
            sentiment, confidence = "neutral", 0.55
        lowered = text.lower()
        if any(term in lowered for term in CHURN_PHRASES):
            intent = "churn_risk"
        elif any(term in lowered for term in ("please add", "feature", "could you", "wish", "it would be great if")):
            intent = "feature_request"
        elif sentiment == "negative":
            intent = "complaint"
        elif sentiment == "positive":
            intent = "praise"
        else:
            intent = "other"
        urgency = "high" if tokens & URGENT else ("medium" if sentiment == "negative" else "low")
        aspect = classify_aspect(text)
        raw = {
            "sentiment": (sentiment, confidence),
            "intent": (intent, 0.72 if intent != "other" else 0.54),
            "urgency": (urgency, 0.78 if urgency != "medium" else 0.64),
            "aspect": (aspect, 0.64 if aspect != "other" else 0.5),
        }
        return {
            task: {
                "label": label,
                "confidence": score,
                "probabilities": self._distribution(label, LABELS[task], score),
            }
            for task, (label, score) in raw.items()
        }

    def predict(self, texts: list[str]) -> list[dict[str, dict[str, Any]]]:
        results = [self._demo_predict(text) for text in texts]
        for task, model in self._task_models.items():
            for index, prediction in enumerate(model.predict(texts)):
                if task in prediction:
                    results[index][task] = prediction[task]
        return results

    def predict_with_shadow(self, texts: list[str]) -> tuple[list[dict], list[dict] | None]:
        primary = self.predict(texts)
        shadow = self.shadow_model.predict(texts) if self.shadow_model else None
        return primary, shadow


def _stamp(model: Any) -> str:
    metadata = getattr(model, "metadata", None)
    if callable(metadata):
        try:
            return str(metadata().get("model_family", "trained"))
        except Exception:  # pragma: no cover - defensive
            return "trained"
    return "trained"
