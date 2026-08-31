"""Dataset drift report with stable, dependency-free distribution metrics."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from insightpulse_modeling.io import read_jsonl


def _distribution(values: list[str], categories: list[str]) -> list[float]:
    counts, total, epsilon = Counter(values), max(len(values), 1), 1e-6
    raw = [(counts.get(category, 0) / total) + epsilon for category in categories]
    normalizer = sum(raw)
    return [value / normalizer for value in raw]


def jensen_shannon(reference: list[float], current: list[float]) -> float:
    midpoint = [(left + right) / 2 for left, right in zip(reference, current)]
    divergence = lambda values: sum(value * math.log(value / middle, 2) for value, middle in zip(values, midpoint))
    return (divergence(reference) + divergence(current)) / 2


def population_stability_index(reference: list[float], current: list[float]) -> float:
    return sum((now - before) * math.log(now / before) for before, now in zip(reference, current))


def length_bucket(text: str) -> str:
    words = len(text.split())
    return "short" if words <= 8 else "long" if words >= 40 else "medium"


def drift_report(reference: list[dict[str, Any]], current: list[dict[str, Any]], threshold: float = 0.2) -> dict[str, Any]:
    features: dict[str, dict[str, Any]] = {}
    extractors = {
        "source": lambda row: str(row.get("source", "unknown")),
        "product": lambda row: str(row.get("product", "unknown")),
        "text_length": lambda row: length_bucket(str(row.get("text", ""))),
    }
    for name, extractor in extractors.items():
        reference_values, current_values = [extractor(row) for row in reference], [extractor(row) for row in current]
        categories = sorted(set(reference_values) | set(current_values))
        before, now = _distribution(reference_values, categories), _distribution(current_values, categories)
        psi, js = population_stability_index(before, now), jensen_shannon(before, now)
        features[name] = {"categories": categories, "reference": dict(zip(categories, before)), "current": dict(zip(categories, now)), "psi": psi, "jensen_shannon": js, "drifted": psi >= threshold}
    return {
        "created_at": datetime.now(UTC).isoformat(), "reference_examples": len(reference),
        "current_examples": len(current), "threshold": threshold,
        "status": "drift_detected" if any(value["drifted"] for value in features.values()) else "ok",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current feedback with a reference dataset")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args()
    report = drift_report(read_jsonl(args.reference), read_jsonl(args.current), args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output)}))
    if args.fail_on_drift and report["status"] != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
