"""CLI for training and evaluating the classical baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baseline import DEFAULT_TASKS, BaselineConfig, SUPPORTED_TASKS
from .runner import train_and_evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Train InsightPulse TF-IDF baselines")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tasks", nargs="+", choices=SUPPORTED_TASKS, default=list(DEFAULT_TASKS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-features", type=int, default=20_000)
    args = parser.parse_args()
    report = train_and_evaluate(
        args.data_dir,
        args.output_dir,
        BaselineConfig(tasks=tuple(args.tasks), seed=args.seed, max_features=args.max_features),
    )
    summary = {
        task: {"examples": values.get("examples"), "macro_f1": values.get("macro_f1")}
        for task, values in report["tasks"].items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
