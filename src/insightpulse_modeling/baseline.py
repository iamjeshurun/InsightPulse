"""Interpretable TF-IDF baselines for the InsightPulse classification tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

_FUNCTION_WORDS = frozenset(
    "a an and are as at be been by for from had has have i in is it me my not of on or "
    "our that the their them they this to was we were with you your".split()
)

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

    def top_terms(self, text: str, task: str, label: str, limit: int = 4) -> list[tuple[str, float]]:
        """Terms that pushed `text` toward `label`: TF-IDF value times the class
        weight, which for a linear model is each term's exact contribution.
        Redaction masks (XXXX) are skipped."""
        model = self.models.get(task)
        if model is None:
            return []
        features = model.named_steps["features"]
        classifier = model.named_steps["classifier"]
        classes = list(classifier.classes_)
        if label not in classes:
            return []
        if len(classes) > 2:
            weights = classifier.coef_[classes.index(label)]
        else:
            weights = classifier.coef_[0] * (1 if classes.index(label) == 1 else -1)
        row = features.transform([text]).tocoo()
        names = features.get_feature_names_out()
        scored = sorted(
            ((str(names[column]), float(value * weights[column])) for column, value in zip(row.col, row.data)),
            key=lambda item: -item[1],
        )
        terms: list[tuple[str, float]] = []
        for term, score in scored:
            if score <= 0.05 or len(terms) == limit:
                break
            tokens = term.split()
            # Skip function-word bigrams ("on my") and terms already covered.
            if tokens[-1] in _FUNCTION_WORDS or all(token in _FUNCTION_WORDS for token in tokens):
                continue
            if any(term in kept or kept in term for kept, _ in terms):
                continue
            # CFPB masks personal details as XXXX; the mask is not readable evidence.
            if all(set(token) == {"x"} for token in tokens):
                continue
            terms.append((term, round(score, 2)))
        return terms

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
