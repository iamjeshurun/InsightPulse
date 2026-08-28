"""Conservative, deterministic PII redaction for customer text."""

from __future__ import annotations

import re

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("PAYMENT_CARD", re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")),
    (
        "CUSTOMER_ID",
        re.compile(r"\b(?:account|customer|order|ticket)[-_ #:]*(?:id[-_ :]*)?[A-Z0-9-]{5,}\b", re.I),
    ),
)


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    redacted = text
    for name, pattern in PATTERNS:
        redacted, count = pattern.subn(f"[{name}]", redacted)
        if count:
            counts[name] = count
    return redacted, counts
