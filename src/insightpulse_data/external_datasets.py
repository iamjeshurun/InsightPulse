"""Adapters for the public benchmark datasets used by InsightPulse.

Raw source files are intentionally excluded from Git.  These adapters preserve
publisher-provided splits where available and emit the JSONL contract consumed
by the modeling package.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

_PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")
_NON_ALPHA = re.compile(r"[^a-z0-9 ]+")


def _template_key(text: str) -> str:
    """Collapse a Bitext instruction to its underlying request.

    Bitext is heavily templated: the same request appears many times with only a
    ``{{placeholder}}`` or light phrasing change.  Splitting on the raw text lets
    those variants leak across train and test.  Grouping on this key keeps every
    variant of one request in the same split.
    """
    lowered = _PLACEHOLDER.sub(" ", text.lower())
    return " ".join(_NON_ALPHA.sub(" ", lowered).split())


DYNASENT_MEMBERS = {
    "train": "dynasent-v1.1/dynasent-v1.1-round02-dynabench-train.jsonl",
    "validation": "dynasent-v1.1/dynasent-v1.1-round02-dynabench-dev.jsonl",
    "test": "dynasent-v1.1/dynasent-v1.1-round02-dynabench-test.jsonl",
}


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_dynasent(archive: Path, output_dir: Path) -> dict[str, Any]:
    """Convert DynaSent Round 2 while retaining its official train/dev/test split."""
    output_dir.mkdir(parents=True, exist_ok=True)
    split_sizes: dict[str, int] = {}
    distributions: dict[str, dict[str, int]] = {}
    with zipfile.ZipFile(archive) as bundle:
        missing = set(DYNASENT_MEMBERS.values()) - set(bundle.namelist())
        if missing:
            raise ValueError(f"DynaSent archive is missing: {sorted(missing)}")
        for split, member in DYNASENT_MEMBERS.items():
            labels: Counter[str] = Counter()

            def records() -> Iterable[dict[str, Any]]:
                with bundle.open(member) as source:
                    for raw_line in source:
                        raw = json.loads(raw_line)
                        label = str(raw["gold_label"])
                        if label not in {"positive", "neutral", "negative"}:
                            continue
                        labels[label] += 1
                        yield {
                            "id": raw["text_id"],
                            "text": raw["sentence"],
                            "source": "review",
                            "product": "DynaSent Round 2",
                            "sentiment": label,
                            "dataset": "dynasent-v1.1-round02",
                        }

            split_sizes[split] = _write_jsonl(output_dir / f"{split}.jsonl", records())
            distributions[split] = dict(sorted(labels.items()))
    metadata = {
        "dataset": "DynaSent v1.1 Round 2",
        "source": "https://github.com/cgpotts/dynasent",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_sha256": _sha256(archive),
        "split_policy": "publisher-provided",
        "split_sizes": split_sizes,
        "label_distributions": distributions,
        "caveat": "The publishers document possible inherited Yelp Academic Dataset terms.",
    }
    (output_dir / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata


def _stable_bucket(value: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def prepare_bitext(source_csv: Path, output_dir: Path, seed: int = 42) -> dict[str, Any]:
    """Convert Bitext intent data into leakage-safe deterministic 80/10/10 splits.

    Records are grouped by their de-templated request key so every phrasing
    variant of one request stays in a single split, and exact-normalized
    duplicates are dropped.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    splits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    distributions: dict[str, Counter[str]] = defaultdict(Counter)
    seen_keys: set[str] = set()
    duplicates = 0
    with source_csv.open(encoding="utf-8", newline="") as handle:
        for index, raw in enumerate(csv.DictReader(handle), start=1):
            intent = str(raw["intent"]).strip().lower()
            text = " ".join(str(raw["instruction"]).split())
            key = _template_key(text)
            dedupe_key = f"{intent}:{key}"
            if dedupe_key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(dedupe_key)
            record_id = f"bitext-{index:05d}"
            bucket = _stable_bucket(key, seed)
            split = "train" if bucket < 80 else "validation" if bucket < 90 else "test"
            splits[split].append(
                {
                    "id": record_id,
                    "text": text,
                    "source": "support_ticket",
                    "product": "Bitext Customer Support",
                    "intent": intent,
                    "intent_category": str(raw["category"]).strip().lower(),
                    "linguistic_flags": str(raw["flags"]).strip(),
                    "dataset": "bitext-customer-support-v11",
                }
            )
            distributions[split][intent] += 1
    split_sizes = {
        split: _write_jsonl(output_dir / f"{split}.jsonl", splits[split])
        for split in ("train", "validation", "test")
    }
    metadata = {
        "dataset": "Bitext Sample Customer Support Training Dataset v11",
        "source": "https://github.com/bitext/customer-support-llm-chatbot-training-dataset",
        "license": "CDLA-Sharing-1.0",
        "license_url": "https://cdla.dev/sharing-1-0/",
        "source_sha256": _sha256(source_csv),
        "seed": seed,
        "split_policy": "deterministic 80/10/10 grouped by de-templated request key",
        "dropped_normalized_duplicates": duplicates,
        "split_sizes": split_sizes,
        "label_distributions": {
            split: dict(sorted(distributions[split].items())) for split in split_sizes
        },
        "caveat": (
            "Publisher describes the examples as hybrid synthetic and linguist-curated; "
            "same-generation train and test still share vocabulary and structure."
        ),
    }
    (output_dir / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata
