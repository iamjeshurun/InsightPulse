"""Prepare licensed external benchmarks without committing their raw text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cfpb import NARRATIVE_CUTOFF, fetch_archived_complaints, prepare_cfpb
from .external_datasets import prepare_bitext, prepare_dynasent


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an InsightPulse benchmark dataset")
    parser.add_argument("dataset", choices=("dynasent", "bitext", "cfpb"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.dataset == "dynasent":
        result = prepare_dynasent(args.input, args.output_dir)
    elif args.dataset == "cfpb":
        result = prepare_cfpb(args.input, args.output_dir, args.seed)
    else:
        result = prepare_bitext(args.input, args.output_dir, args.seed)
    print(json.dumps(result, indent=2, sort_keys=True))


def cfpb_fetch_main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a slice of archived CFPB complaint narratives (complaints received through "
            f"{NARRATIVE_CUTOFF.isoformat()}; CFPB no longer publishes newer narratives)."
        )
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--date-min", required=True, help="first date received, inclusive (YYYY-MM-DD)")
    parser.add_argument("--date-max", required=True, help="last date received, exclusive (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--products", nargs="*", default=[])
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/cfpb-archive"))
    args = parser.parse_args()
    try:
        result = fetch_archived_complaints(
            args.output,
            date_min=args.date_min,
            date_max=args.date_max,
            limit=args.limit,
            products=tuple(args.products),
            cache_dir=args.cache_dir,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
