"""End-to-end baseline training, evaluation, and artifact generation."""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import sklearn

from .baseline import BaselineConfig, BaselineSuite
from .evaluation import evaluate_task
from .io import read_jsonl, write_json, write_jsonl


def _model_card(report: dict[str, Any]) -> str:
    task_rows = "\n".join(
        f"| {task} | {metrics.get('examples', 0)} | {metrics.get('macro_f1', 'n/a')} | "
        f"{metrics.get('expected_calibration_error', 'n/a')} |"
        for task, metrics in report["tasks"].items()
    )
    return f"""# Model Card: InsightPulse TF-IDF Baseline

## Overview

This artifact is an interpretable classical baseline using word and bigram
TF-IDF features with one class-balanced logistic-regression classifier per
task. Its purpose is to establish a reproducible lower bound for transformer
experiments—not to serve as a universal sentiment model.

## Evaluation

| Task | Test examples | Macro-F1 | Expected calibration error |
| --- | ---: | ---: | ---: |
{task_rows}

Mean inference latency: {report['latency']['mean_ms_per_example']:.4f} ms/example.

## Appropriate use

Use for experimentation on English-language customer feedback resembling the
training domain. Predictions should support human decisions, not make automated
employment, credit, medical, legal, or other high-impact decisions.

## Limitations

- Small or unrepresentative test sets cannot support reliable performance claims.
- Lexical models struggle with sarcasm, implicit sentiment, and domain shift.
- Probability calibration and subgroup performance require ongoing monitoring.
- PII redaction and dataset licensing remain upstream responsibilities.

## Reproducibility

Random seed: `{report['reproducibility']['seed']}`  
Python: `{report['reproducibility']['python']}`  
scikit-learn: `{report['reproducibility']['scikit_learn']}`
"""


def train_and_evaluate(
    data_dir: Path, output_dir: Path, config: BaselineConfig | None = None
) -> dict[str, Any]:
    config = config or BaselineConfig()
    train = read_jsonl(data_dir / "train.jsonl")
    validation = read_jsonl(data_dir / "validation.jsonl")
    test = read_jsonl(data_dir / "test.jsonl")
    suite = BaselineSuite(config).fit(train)

    validation_predictions = suite.predict([str(record["text"]) for record in validation])
    test_predictions = suite.predict([str(record["text"]) for record in test])
    report = {
        "model": suite.metadata(),
        "created_at": datetime.now(UTC).isoformat(),
        "split_sizes": {"train": len(train), "validation": len(validation), "test": len(test)},
        "validation": {
            task: evaluate_task(validation, validation_predictions, task) for task in config.tasks
        },
        "tasks": {task: evaluate_task(test, test_predictions, task) for task in config.tasks},
        "latency": suite.benchmark([str(record["text"]) for record in test]),
        "reproducibility": {
            "seed": config.seed,
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(suite, output_dir / "baseline.joblib")
    write_json(output_dir / "evaluation_report.json", report)
    write_jsonl(
        output_dir / "test_predictions.jsonl",
        [
            {"id": record["id"], "labels": prediction}
            for record, prediction in zip(test, test_predictions)
        ],
    )
    (output_dir / "model_card.md").write_text(_model_card(report), encoding="utf-8")
    (output_dir / "run_config.json").write_text(
        json.dumps(suite.metadata(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
