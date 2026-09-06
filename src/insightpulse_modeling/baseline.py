"""Interpretable TF-IDF baselines for the InsightPulse classification tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

DEFAULT_TASKS = ("sentiment", "intent", "urgency")
SUPPORTED_TASKS = (*DEFAULT_TASKS, "aspect")


@dataclass(frozen=True)
class BaselineConfig:
    tasks: tuple[str, ...] = DEFAULT_TASKS
    seed: int = 42
    max_features: int = 20_000
    min_df: int = 1
    class_weight: str | None = "balanced"

    def validate(self) -> None:
        unknown = set(self.tasks) - set(SUPPORTED_TASKS)
        if unknown:
            raise ValueError(f"unsupported tasks: {sorted(unknown)}")
        if not self.tasks:
            raise ValueError("at least one task is required")


class BaselineSuite:
    """One independently inspectable classifier per output task."""

    def __init__(self, config: BaselineConfig | None = None) -> None:
        self.config = config or BaselineConfig()
        self.config.validate()
        self.models: dict[str, Pipeline] = {}

    @staticmethod
    def _pipeline(config: BaselineConfig) -> Pipeline:
        return Pipeline(
            [
                (
                    "features",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=config.min_df,
                        max_features=config.max_features,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight=config.class_weight,
                        max_iter=1_000,
                        random_state=config.seed,
                    ),
                ),
            ]
        )

    def fit(self, records: list[dict[str, Any]]) -> "BaselineSuite":
        texts = [str(record["text"]) for record in records]
        if not texts:
            raise ValueError("training records cannot be empty")
        for task in self.config.tasks:
            labeled = [(text, record.get(task)) for text, record in zip(texts, records) if record.get(task)]
            labels = {label for _, label in labeled}
            if len(labels) < 2:
                raise ValueError(f"task {task!r} requires at least two classes in the training split")
            model = self._pipeline(self.config)
            model.fit([text for text, _ in labeled], [label for _, label in labeled])
            self.models[task] = model
        return self

    def predict(self, texts: list[str]) -> list[dict[str, dict[str, Any]]]:
        if set(self.models) != set(self.config.tasks):
            raise RuntimeError("model suite has not been fitted")
        results: list[dict[str, dict[str, Any]]] = [{} for _ in texts]
        for task, model in self.models.items():
            probabilities = model.predict_proba(texts)
            classes = list(model.named_steps["classifier"].classes_)
            for index, row in enumerate(probabilities):
                best = int(np.argmax(row))
                results[index][task] = {
                    "label": str(classes[best]),
                    "confidence": float(row[best]),
                    "probabilities": {str(label): float(score) for label, score in zip(classes, row)},
                }
        return results

    def benchmark(self, texts: list[str], repeats: int = 5) -> dict[str, float]:
        if not texts:
            return {"examples": 0, "mean_ms_per_example": 0.0, "p95_ms_per_example": 0.0}
        timings: list[float] = []
        for _ in range(repeats):
            started = perf_counter()
            self.predict(texts)
            timings.append((perf_counter() - started) * 1_000 / len(texts))
        return {
            "examples": len(texts),
            "mean_ms_per_example": float(np.mean(timings)),
            "p95_ms_per_example": float(np.percentile(timings, 95)),
        }

    def metadata(self) -> dict[str, Any]:
        return {"model_family": "tfidf_logistic_regression", "config": asdict(self.config)}
