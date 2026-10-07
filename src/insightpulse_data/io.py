"""Shared file, hashing, and split helpers for the data and modeling packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_fingerprint(text: str) -> str:
    """Case- and whitespace-insensitive hash used for duplicate detection."""
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


def stable_bucket(value: str, seed: int) -> int:
    """Deterministic bucket in [0, 100) for leakage-safe splits."""
    return int(hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()[:8], 16) % 100
