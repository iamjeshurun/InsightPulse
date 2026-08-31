"""Model loading and safe local demo inference."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib

POSITIVE = {"excellent", "great", "love", "fast", "helpful", "clear", "wonderful", "solved", "professional"}
NEGATIVE = {"broken", "bad", "hate", "slow", "freeze", "freezes", "charged", "locked", "cancel", "fails", "failed"}
URGENT = {"urgent", "immediately", "outage", "security", "charged", "locked", "cancel"}


class ModelService:
    def __init__(self, model_path: Path | None = None) -> None:
        configured = model_path or (Path(os.environ["INSIGHTPULSE_MODEL_PATH"]) if os.getenv("INSIGHTPULSE_MODEL_PATH") else None)
        self.model = joblib.load(configured) if configured and configured.exists() else None
        self.version = f"baseline:{configured.name}" if self.model else "demo-lexicon-1"
        shadow_path = Path(os.environ["INSIGHTPULSE_SHADOW_MODEL_PATH"]) if os.getenv("INSIGHTPULSE_SHADOW_MODEL_PATH") else None
        self.shadow_model = joblib.load(shadow_path) if shadow_path and shadow_path.exists() else None

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
        if any(term in lowered for term in ("cancel", "leave", "switch provider")):
            intent = "churn_risk"
        elif any(term in lowered for term in ("please add", "feature", "could you", "wish")):
            intent = "feature_request"
        elif sentiment == "negative":
            intent = "complaint"
        elif sentiment == "positive":
            intent = "praise"
        else:
            intent = "other"
        urgency = "high" if tokens & URGENT else ("medium" if sentiment == "negative" else "low")
        return {
            "sentiment": {
                "label": sentiment,
                "confidence": confidence,
                "probabilities": self._distribution(sentiment, ["negative", "neutral", "positive"], confidence),
            },
            "intent": {
                "label": intent,
                "confidence": 0.72 if intent != "other" else 0.54,
                "probabilities": self._distribution(
                    intent, ["churn_risk", "complaint", "feature_request", "other", "praise"], 0.72 if intent != "other" else 0.54
                ),
            },
            "urgency": {
                "label": urgency,
                "confidence": 0.78 if urgency != "medium" else 0.64,
                "probabilities": self._distribution(urgency, ["high", "low", "medium"], 0.78 if urgency != "medium" else 0.64),
            },
        }

    def predict(self, texts: list[str]) -> list[dict[str, dict[str, Any]]]:
        if self.model:
            return self.model.predict(texts)
        return [self._demo_predict(text) for text in texts]

    def predict_with_shadow(self, texts: list[str]) -> tuple[list[dict], list[dict] | None]:
        primary = self.predict(texts)
        shadow = self.shadow_model.predict(texts) if self.shadow_model else None
        return primary, shadow
