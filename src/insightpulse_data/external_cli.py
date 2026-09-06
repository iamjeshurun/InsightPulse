"""Prepare licensed external benchmarks without committing their raw text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .external_datasets import prepare_bitext, prepare_dynasent


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an InsightPulse benchmark dataset")
    parser.add_argument("dataset", choices=("dynasent", "bitext"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.dataset == "dynasent":
        result = prepare_dynasent(args.input, args.output_dir)
    else:
        result = prepare_bitext(args.input, args.output_dir, args.seed)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
