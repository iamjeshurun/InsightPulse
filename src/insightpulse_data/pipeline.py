"""Deterministic ingestion and quality pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import FeedbackRecord, parse_record
from .privacy import redact_pii


@dataclass(frozen=True)
class PipelineConfig:
    dataset_name: str
    dataset_version: str
    seed: int = 42
    train_ratio: float = 0.8
    validation_ratio: float = 0.1

    def validate(self) -> None:
        if not self.dataset_name.strip() or not self.dataset_version.strip():
            raise ValueError("dataset name and version are required")
        if not 0 < self.train_ratio < 1:
            raise ValueError("train_ratio must be between 0 and 1")
        if not 0 <= self.validation_ratio < 1:
            raise ValueError("validation_ratio must be between 0 and 1")
        if self.train_ratio + self.validation_ratio >= 1:
            raise ValueError("train and validation ratios must leave a test split")


def load_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    raise ValueError("input must be a .csv or .jsonl file")


def _fingerprint(text: str) -> str:
    canonical = " ".join(text.lower().split())
    return hashlib.sha256(canonical.encode()).hexdigest()


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split(records: list[dict[str, Any]], config: PipelineConfig) -> dict[str, list[dict[str, Any]]]:
    shuffled = sorted(records, key=lambda row: row["id"])
    random.Random(config.seed).shuffle(shuffled)
    size = len(shuffled)
    train_end = round(size * config.train_ratio)
    validation_end = train_end + round(size * config.validation_ratio)
    return {
        "train": shuffled[:train_end],
        "validation": shuffled[train_end:validation_end],
        "test": shuffled[validation_end:],
    }


def _distribution(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unlabeled") for row in records).items()))


def _dataset_card(config: PipelineConfig, source: Path, report: dict[str, Any]) -> str:
    return f"""# Dataset Card: {config.dataset_name}

## Version

{config.dataset_version}

## Source and intended use

Processed from `{source.name}` for development and evaluation of the InsightPulse
voice-of-customer pipeline. Confirm the original dataset's license and terms
before redistribution or commercial use.

## Processing

- Schema validation and whitespace normalization
- Regex-based PII redaction
- Exact duplicate removal after normalization and redaction
- Deterministic train/validation/test split using seed `{config.seed}`
- Invalid records isolated in `quarantine.jsonl`

## Statistics

- Input records: {report['counts']['input']}
- Accepted unique records: {report['counts']['accepted']}
- Invalid records: {report['counts']['invalid']}
- Duplicate records: {report['counts']['duplicates']}
- Split sizes: {json.dumps(report['split_sizes'], sort_keys=True)}
- Sentiment distribution: {json.dumps(report['distributions']['sentiment'], sort_keys=True)}

## Limitations and risks

This dataset may encode sampling, demographic, language, and annotation bias.
Regex redaction cannot identify every form of personal information. Labels must
not be treated as ground truth without inter-annotator checks. Before release,
evaluate performance by source, product, language, class, and relevant user
groups, and document known failure modes.
"""


def run_pipeline(input_path: Path, output_dir: Path, config: PipelineConfig) -> dict[str, Any]:
    config.validate()
    raw_records = load_records(input_path)
    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    duplicates = 0
    redactions: Counter[str] = Counter()

    for row_number, raw in enumerate(raw_records, start=2):
        parsed, errors = parse_record(raw)
        if errors:
            quarantined.append({"row": row_number, "errors": errors, "record": raw})
            continue
        assert isinstance(parsed, FeedbackRecord)
        redacted_text, record_redactions = redact_pii(parsed.text)
        fingerprint = _fingerprint(redacted_text)
        if parsed.id in seen_ids or fingerprint in seen_text:
            duplicates += 1
            continue
        seen_ids.add(parsed.id)
        seen_text.add(fingerprint)
        redactions.update(record_redactions)
        record = parsed.to_dict()
        record["text"] = redacted_text
        record["text_sha256"] = fingerprint
        accepted.append(record)

    splits = _split(accepted, config)
    report = {
        "dataset": {"name": config.dataset_name, "version": config.dataset_version},
        "counts": {
            "input": len(raw_records),
            "accepted": len(accepted),
            "invalid": len(quarantined),
            "duplicates": duplicates,
        },
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "distributions": {
            field: _distribution(accepted, field)
            for field in ("source", "product", "sentiment", "intent", "urgency")
        },
        "redactions": dict(sorted(redactions.items())),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[Path] = []
    for split_name, rows in splits.items():
        split_path = output_dir / f"{split_name}.jsonl"
        _write_jsonl(split_path, rows)
        output_files.append(split_path)
    quarantine_path = output_dir / "quarantine.jsonl"
    _write_jsonl(quarantine_path, quarantined)
    output_files.append(quarantine_path)
    report_path = output_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_files.append(report_path)
    card_path = output_dir / "dataset_card.md"
    card_path.write_text(_dataset_card(config, input_path, report), encoding="utf-8")
    output_files.append(card_path)
    manifest = {
        "dataset": report["dataset"],
        "created_at": datetime.now(UTC).isoformat(),
        "seed": config.seed,
        "source_sha256": _checksum(input_path),
        "files": {path.name: _checksum(path) for path in output_files},
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
