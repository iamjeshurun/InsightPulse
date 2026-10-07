"""Ingestion and labeling for public CFPB consumer complaint narratives."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import httpx

from .io import sha256_file, stable_bucket, text_fingerprint
from .privacy import redact_pii

# CFPB stopped publishing complaint narratives in its live database and API on
# 2026-08-14 and moved every previously published narrative to a FOIA archive of
# bulk exports, split by date received. No newer narratives are published.
ARCHIVE_PAGE_URL = (
    "https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/"
    "cfpb-consumer-complaint-database-narratives-archive/"
)
ARCHIVE_BASE_URL = "https://files.consumerfinance.gov/f/documents/"
ARCHIVE_FIRST_DATE = date(2011, 12, 1)
NARRATIVE_CUTOFF = date(2026, 8, 14)
DEFAULT_ARCHIVE_CACHE = Path("data/raw/cfpb-archive")
# (file stem, first month received, last month received)
ARCHIVE_EXPORTS: tuple[tuple[str, str, str], ...] = (
    ("CCDB_Export_1_December_2011_through_April_2018", "2011-12", "2018-04"),
    ("CCDB_Export_2_May_2018_through_April_2021", "2018-05", "2021-04"),
    ("CCDB_Export_3_May_2021_through_October_2022", "2021-05", "2022-10"),
    ("CCDB_Export_4_November_2022_through_August_2023", "2022-11", "2023-08"),
    ("CCDB_Export_5_September_2023_through_March_2024", "2023-09", "2024-03"),
    ("CCDB_Export_6_April_2024_through_July_2024", "2024-04", "2024-07"),
    ("CCDB_Export_7_August_2024_through_October_2024", "2024-08", "2024-10"),
    ("CCDB_Export_8_November_2024_through_December_2024", "2024-11", "2024-12"),
    ("CCDB_Export_9_January_2025_through_February_2025", "2025-01", "2025-02"),
    ("CCDB_Export_10_March_2025_through_April_2025", "2025-03", "2025-04"),
    ("CCDB_Export_11_May_2025_through_June_2025", "2025-05", "2025-06"),
    ("CCDB_Export_12_July_2025_through_August_2025", "2025-07", "2025-08"),
    ("CCDB_Export_13_September_2025_through_October_2025", "2025-09", "2025-10"),
    ("CCDB_Export_14_November_2025_through_December_2025", "2025-11", "2025-12"),
    ("CCDB_Export_15_January_2026_through_February_2026", "2026-01", "2026-02"),
    ("CCDB_Export_16_March_2026", "2026-03", "2026-03"),
    ("CCDB_Export_17_April_2026", "2026-04", "2026-04"),
    ("CCDB_Export_18_May_2026", "2026-05", "2026-05"),
    ("CCDB_Export_19_June_2026", "2026-06", "2026-06"),
    ("CCDB_Export_20_July_2026", "2026-07", "2026-07"),
    ("CCDB_Export_21_August_2026", "2026-08", "2026-08"),
)

# Ordered rules translate the consumer-selected CFPB issue into a compact
# business taxonomy. The original issue and sub-issue remain available for
# auditing; no model predictions are used to manufacture these labels.
ASPECT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fraud_security", ("identity theft", "fraud", "scam", "unauthorized", "stolen")),
    ("credit_reporting", ("credit report", "credit score", "incorrect information")),
    ("payments", ("payment", "cash", "transfer", "deposit", "withdraw")),
    ("fees_interest", ("fee", "interest", "overdraft", "pricing")),
    ("account_access", ("account", "login", "password", "card activation", "cash access")),
    ("debt_collection", ("debt", "collector", "collection")),
    ("loan_servicing", ("loan", "mortgage", "foreclosure", "repay", "servicing")),
)


def classify_aspect(issue: str, sub_issue: str = "", product: str = "") -> str:
    searchable = " ".join((issue, sub_issue, product)).lower()
    for aspect, terms in ASPECT_RULES:
        if any(term in searchable for term in terms):
            return aspect
    return "other"


def _month(value: str) -> tuple[int, int]:
    year, month = value.split("-")[:2]
    return int(year), int(month)


def archive_exports_for(date_min: str, date_max: str) -> list[str]:
    """Archive export files whose received-date months overlap [date_min, date_max)."""
    start = date.fromisoformat(date_min)
    end = date.fromisoformat(date_max)
    if end <= start:
        raise ValueError("date_max must be after date_min")
    if start < ARCHIVE_FIRST_DATE:
        raise ValueError(f"The narratives archive starts at complaints received {ARCHIVE_FIRST_DATE.isoformat()}.")
    if end > NARRATIVE_CUTOFF + timedelta(days=1):
        raise ValueError(
            f"CFPB stopped publishing complaint narratives on {NARRATIVE_CUTOFF.isoformat()}. The archive covers "
            f"complaints received {ARCHIVE_FIRST_DATE.isoformat()} through {NARRATIVE_CUTOFF.isoformat()}, and no "
            f"newer narratives are published. Use a date_max of {(NARRATIVE_CUTOFF + timedelta(days=1)).isoformat()} "
            "or earlier (date_max is exclusive)."
        )
    last = end - timedelta(days=1)
    wanted = []
    for stem, first_month, last_month in ARCHIVE_EXPORTS:
        if _month(first_month) <= (last.year, last.month) and (start.year, start.month) <= _month(last_month):
            wanted.append(stem)
    return wanted


def _download_export(stem: str, cache_dir: Path) -> Path:
    path = cache_dir / f"{stem}.zip"
    if path.exists() and zipfile.is_zipfile(path):
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".zip.part")
    with httpx.stream("GET", f"{ARCHIVE_BASE_URL}{stem}.zip", timeout=120, follow_redirects=True) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    partial.replace(path)
    return path


def _archive_rows(path: Path) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        name = next(member for member in archive.namelist() if member.lower().endswith(".csv"))
        with archive.open(name) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))


def fetch_archived_complaints(
    output_path: Path,
    *,
    date_min: str,
    date_max: str,
    limit: int = 10_000,
    products: tuple[str, ...] = (),
    cache_dir: Path = DEFAULT_ARCHIVE_CACHE,
) -> dict[str, Any]:
    """Write a date-bounded slice of archived complaint narratives as JSONL.

    Reads CFPB's FOIA narratives archive (narratives published before
    publication stopped on 2026-08-14). ``date_max`` is exclusive. Records are
    taken oldest first; with ``products`` they are taken round-robin across those
    products so no single product dominates. Downloaded exports are cached in
    ``cache_dir`` and reused.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    stems = archive_exports_for(date_min, date_max)
    start, end = date.fromisoformat(date_min), date.fromisoformat(date_max)
    wanted = set(products)
    by_product: dict[str, list[dict[str, str]]] = {}
    seen: set[str] = set()
    scanned = duplicates = 0
    for stem in stems:
        for raw in _archive_rows(_download_export(stem, cache_dir)):
            narrative = (raw.get("Consumer complaint narrative") or "").strip()
            received = (raw.get("Date received") or "")[:10]
            if not narrative or not received or not start <= date.fromisoformat(received) < end:
                continue
            product = raw.get("Product") or ""
            if wanted and product not in wanted:
                continue
            scanned += 1
            fingerprint = text_fingerprint(narrative)
            if fingerprint in seen:
                duplicates += 1
                continue
            seen.add(fingerprint)
            # Whitelist fields: intentionally omit company, state, ZIP and tags.
            by_product.setdefault(product if wanted else "", []).append(
                {
                    "complaint_id": raw.get("Complaint ID", ""),
                    "narrative": narrative,
                    "date_received": received,
                    "product": product,
                    "sub_product": raw.get("Sub-product") or "",
                    "issue": raw.get("Issue") or "",
                    "sub_issue": raw.get("Sub-issue") or "",
                }
            )
    queues = [
        sorted(rows, key=lambda row: (row["date_received"], int(row["complaint_id"] or 0)))
        for _, rows in sorted(by_product.items())
    ]
    selected: list[dict[str, str]] = []
    position = 0
    while len(selected) < limit and any(position < len(queue) for queue in queues):
        for queue in queues:
            if position < len(queue) and len(selected) < limit:
                selected.append(queue[position])
        position += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    result = {
        "query": {
            "date_received_min": date_min,
            "date_received_max_exclusive": date_max,
            "products": list(products),
            "sampling": "round-robin by product, oldest first" if products else "oldest first",
        },
        "archive_exports": stems,
        "matching_narratives": scanned,
        "skipped_exact_duplicates": duplicates,
        "retained_narratives": len(selected),
        "target_narratives": limit,
        "target_reached": len(selected) >= limit,
        "source": ARCHIVE_PAGE_URL,
        "narrative_cutoff": NARRATIVE_CUTOFF.isoformat(),
        "license": "Public domain (CFPB FOIA reading room)",
    }
    result["output_sha256"] = sha256_file(output_path)
    metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    metadata_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _bucket(identifier: str, seed: int) -> str:
    value = stable_bucket(identifier, seed)
    return "train" if value < 80 else "validation" if value < 90 else "test"


def _source_rows(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            for raw in csv.DictReader(handle):
                yield {
                    "complaint_id": raw.get("Complaint ID", ""),
                    "narrative": raw.get("Consumer complaint narrative", ""),
                    "date_received": str(raw.get("Date received", ""))[:10],
                    "product": raw.get("Product", ""),
                    "sub_product": raw.get("Sub-product", ""),
                    "issue": raw.get("Issue", ""),
                    "sub_issue": raw.get("Sub-issue", ""),
                }
        return
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return
    raise ValueError("CFPB source must be a .csv bulk export or .jsonl API snapshot")


def prepare_cfpb(source_jsonl: Path, output_dir: Path, seed: int = 42) -> dict[str, Any]:
    """Redact and convert downloaded narratives into aspect-classification splits."""
    splits: dict[str, list[dict[str, Any]]] = {name: [] for name in ("train", "validation", "test")}
    labels: Counter[str] = Counter()
    redactions: Counter[str] = Counter()
    seen: set[str] = set()
    skipped = 0
    for raw in _source_rows(source_jsonl):
        text, found = redact_pii(str(raw.get("narrative") or ""))
        fingerprint = text_fingerprint(text)
        if len(text) < 20 or fingerprint in seen:
            skipped += 1
            continue
        seen.add(fingerprint)
        redactions.update(found)
        aspect = classify_aspect(
            str(raw.get("issue") or ""),
            str(raw.get("sub_issue") or ""),
            str(raw.get("product") or ""),
        )
        labels[aspect] += 1
        identifier = f"cfpb-{raw['complaint_id']}"
        splits[_bucket(identifier, seed)].append(
            {
                "id": identifier,
                "text": text,
                "source": "support_ticket",
                "product": raw.get("product", "Financial product"),
                "created_at": raw.get("date_received", ""),
                "aspect": aspect,
                "issue": raw.get("issue", ""),
                "sub_issue": raw.get("sub_issue", ""),
                "dataset": "cfpb-public-complaints",
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        with (output_dir / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    metadata = {
        "dataset": "CFPB public consumer complaint narratives",
        "source": ARCHIVE_PAGE_URL,
        "license": "Public domain (CFPB FOIA reading room)",
        "seed": seed,
        "source_sha256": sha256_file(source_jsonl),
        "split_sizes": {name: len(rows) for name, rows in splits.items()},
        "aspect_distribution": dict(sorted(labels.items())),
        "redactions": dict(sorted(redactions.items())),
        "skipped_short_or_duplicate": skipped,
        "limitations": [
            "Complaints are unverified and represent one side of a dispute.",
            "The corpus is strongly negative and is not used to train overall sentiment.",
            "Aspect labels are deterministic groupings of consumer-selected CFPB issue fields.",
        ],
    }
    (output_dir / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata
