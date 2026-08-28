"""Command-line entry point for the data pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import PipelineConfig, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare an InsightPulse feedback dataset")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = PipelineConfig(
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
        seed=args.seed,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
    )
    report = run_pipeline(args.input, args.output_dir, config)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
