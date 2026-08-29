"""Task metrics, calibration analysis, and behavioral error slices."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

NEGATION_TERMS = {"not", "no", "never", "neither", "hardly", "without", "isn't", "wasn't", "don't", "didn't"}


def expected_calibration_error(confidences: list[float], correct: list[bool], bins: int = 10) -> float:
    if not confidences:
        return 0.0
    confidence_array = np.asarray(confidences)
    correct_array = np.asarray(correct, dtype=float)
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for index in range(bins):
        lower, upper = boundaries[index], boundaries[index + 1]
        mask = (confidence_array > lower) & (confidence_array <= upper)
        if mask.any():
            error += float(mask.mean() * abs(correct_array[mask].mean() - confidence_array[mask].mean()))
    return error


def behavior_slice(text: str) -> str:
    tokens = set(text.lower().replace(".", "").replace(",", "").split())
    if tokens & NEGATION_TERMS:
        return "negation"
    if "?" in text:
        return "question"
    word_count = len(text.split())
    if word_count <= 8:
        return "short"
    if word_count >= 40:
        return "long"
    return "standard"


def evaluate_task(
    records: list[dict[str, Any]], predictions: list[dict[str, dict[str, Any]]], task: str
) -> dict[str, Any]:
    evaluated = [
        (record, prediction[task])
        for record, prediction in zip(records, predictions)
        if record.get(task) and task in prediction
    ]
    if not evaluated:
        return {"examples": 0, "status": "no_labeled_examples"}
    truth = [str(record[task]) for record, _ in evaluated]
    predicted = [str(result["label"]) for _, result in evaluated]
    labels = sorted(set(truth) | set(predicted))
    confidences = [float(result["confidence"]) for _, result in evaluated]
    correct = [actual == estimate for actual, estimate in zip(truth, predicted)]

    slices: dict[str, list[bool]] = defaultdict(list)
    errors: list[dict[str, Any]] = []
    for (record, result), is_correct in zip(evaluated, correct):
        bucket = behavior_slice(str(record["text"]))
        slices[bucket].append(is_correct)
        if not is_correct:
            errors.append(
                {
                    "id": record["id"],
                    "text": record["text"],
                    "expected": record[task],
                    "predicted": result["label"],
                    "confidence": result["confidence"],
                    "slice": bucket,
                }
            )
    return {
        "examples": len(evaluated),
        "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1": float(f1_score(truth, predicted, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(truth, predicted, labels=labels, average="weighted", zero_division=0)),
        "expected_calibration_error": expected_calibration_error(confidences, correct),
        "labels": labels,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
        "per_class": classification_report(
            truth, predicted, labels=labels, output_dict=True, zero_division=0
        ),
        "behavior_slices": {
            name: {"examples": len(values), "accuracy": sum(values) / len(values)}
            for name, values in sorted(slices.items())
        },
        "errors": errors,
    }
