"""Ingestion and labeling for public CFPB consumer complaint narratives."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import httpx

from .privacy import redact_pii

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

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


def _search_after(hit: dict[str, Any]) -> str | None:
    token = hit.get("sort")
    if not token:
        return None
    return "_".join(str(part) for part in token)


def fetch_public_complaints(
    output_path: Path,
    *,
    date_min: str,
    date_max: str,
    limit: int = 10_000,
    page_size: int = 100,
    products: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Fetch a date-bounded slice of complaints that carry a public narrative.

    Deep pagination uses the CFPB API's ``search_after`` cursor (its ``frm``
    offset parameter is capped at a single page), so the collector can walk the
    whole date window.  With no ``products`` filter it pages one time-ordered
    stream; with one or more it round-robins across them so no single product
    dominates the sample.
    """
    if limit < 1 or not 1 <= page_size <= 100:
        raise ValueError("limit must be positive and page_size must be between 1 and 100")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fetched = retained = duplicate_narratives = 0
    seen_narratives: set[str] = set()
    product_filters: tuple[str | None, ...] = products or (None,)
    cursors: dict[str | None, str | None] = {product: None for product in product_filters}
    exhausted: set[str | None] = set()
    with (
        httpx.Client(
            headers={"User-Agent": "InsightPulse/0.7 research"},
            timeout=60,
            follow_redirects=True,
        ) as client,
        output_path.open("w", encoding="utf-8") as handle,
    ):
        while retained < limit and len(exhausted) < len(product_filters):
            for product_filter in product_filters:
                if retained >= limit or product_filter in exhausted:
                    continue
                params: dict[str, Any] = {
                    "date_received_min": date_min,
                    "date_received_max": date_max,
                    "has_narrative": "true",
                    "sort": "created_date_asc",
                    "size": page_size,
                    "no_aggs": "true",
                    "no_highlight": "true",
                }
                if cursors[product_filter]:
                    params["search_after"] = cursors[product_filter]
                if product_filter:
                    params["product"] = product_filter
                response = client.get(API_URL, params=params)
                response.raise_for_status()
                hits = response.json().get("hits", {}).get("hits", [])
                if not hits:
                    exhausted.add(product_filter)
                    continue
                cursors[product_filter] = _search_after(hits[-1])
                fetched += len(hits)
                if len(hits) < page_size or cursors[product_filter] is None:
                    exhausted.add(product_filter)
                for hit in hits:
                    source = hit.get("_source", {})
                    narrative = str(source.get("complaint_what_happened") or "").strip()
                    if not narrative:
                        continue
                    fingerprint = hashlib.sha256(" ".join(narrative.lower().split()).encode()).hexdigest()
                    if fingerprint in seen_narratives:
                        duplicate_narratives += 1
                        continue
                    seen_narratives.add(fingerprint)
                    # Whitelist fields: intentionally omit company, state, ZIP and tags.
                    row = {
                        "complaint_id": str(source.get("complaint_id", "")),
                        "narrative": narrative,
                        "date_received": str(source.get("date_received", ""))[:10],
                        "product": str(source.get("product") or ""),
                        "sub_product": str(source.get("sub_product") or ""),
                        "issue": str(source.get("issue") or ""),
                        "sub_issue": str(source.get("sub_issue") or ""),
                    }
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    retained += 1
                    if retained >= limit:
                        break
    result = {
        "query": {
            "date_received_min": date_min,
            "date_received_max": date_max,
            "has_narrative": True,
            "products": list(products),
            "sampling": (
                "round-robin by product, ascending created date"
                if products
                else "single stream, ascending created date"
            ),
            "page_size": page_size,
            "pagination": "search_after cursor",
        },
        "fetched": fetched,
        "retained_narratives": retained,
        "target_narratives": limit,
        "target_reached": retained >= limit,
        "skipped_exact_duplicates": duplicate_narratives,
        "source": API_URL,
        "license": "CC0",
    }
    result["output_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    metadata_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _bucket(identifier: str, seed: int) -> str:
    value = int(hashlib.sha256(f"{seed}:{identifier}".encode()).hexdigest()[:8], 16) % 100
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
        fingerprint = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()
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
        "source": API_URL,
        "license": "CC0",
        "seed": seed,
        "source_sha256": hashlib.sha256(source_jsonl.read_bytes()).hexdigest(),
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
