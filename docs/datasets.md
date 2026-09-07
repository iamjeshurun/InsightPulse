# Benchmark datasets and licensing

InsightPulse does not commit third-party raw text. The preparation command
converts publisher downloads into the internal JSONL contract and records the
source checksum, split policy, label counts, URL, license, and known caveats.

## DynaSent v1.1 Round 2 — overall sentiment

- Purpose: three-class positive, neutral, and negative sentiment.
- Why Round 2: difficult examples written by crowdworkers and official splits.
- License stated by publisher: CC BY 4.0.
- Important caveat: the DynaSent authors say many Round 2 examples were created
  from Yelp-derived prompts and cannot adjudicate whether Yelp terms carry over.
  This project therefore downloads the data at build time and does not
  redistribute it.

## Bitext Customer Support v11 — intent

- Purpose: 27 customer-support intents across 10 categories.
- Size stated by publisher: 26,872 examples.
- License stated by publisher: CDLA-Sharing 1.0.
- Provenance: hybrid synthetic examples generated with Bitext technology and
  curated by computational linguists; results may not transfer to organic
  production tickets.
- Split: deterministic 80/10/10 hash split seeded with 42. The intent is part
  of the hash input, which keeps every class distributed without using text
  order from the source CSV.

## Reproduction

Download the source files into `data/raw/` and run:

```bash
insightpulse-prepare-benchmark dynasent \
  --input data/raw/dynasent/dynasent-v1.1.zip \
  --output-dir artifacts/benchmarks/dynasent

insightpulse-prepare-benchmark bitext \
  --input data/raw/bitext/customer-support.csv \
  --output-dir artifacts/benchmarks/bitext
```

Then train task-specific baselines:

```bash
insightpulse-baseline --data-dir artifacts/benchmarks/dynasent \
  --output-dir artifacts/models/dynasent-baseline --tasks sentiment

insightpulse-baseline --data-dir artifacts/benchmarks/bitext \
  --output-dir artifacts/models/bitext-baseline --tasks intent
```

Dataset licenses apply to the datasets. The repository's MIT license applies
only to original InsightPulse code and documentation.

## CFPB public complaints — aspect classification

- Purpose: real customer-language classification into account access, credit
  reporting, debt collection, fees and interest, fraud and security, loan
  servicing, payments, and other. Categories with inadequate support are
  merged into `other` before evaluation.
- Source: the U.S. Consumer Financial Protection Bureau public API.
- License reported by the API: CC0.
- Labels: deterministic groupings of the consumer-selected `issue`,
  `sub_issue`, and `product` fields. They are traceable weak supervision, not
  AI-generated annotations.
- Privacy: only complaint ID, narrative, date, product, and issue fields are
  downloaded. Company, state, ZIP code, and demographic tags are excluded.
  InsightPulse performs a second pass of PII redaction before modeling.
- Sampling: fixed dates, ascending time order, round-robin product filters,
  exact deduplication during collection, and a bounded number of API pages.

The measured baseline uses the fixed January 2019 bulk CSV export, whose source
SHA-256 is `88f75a07ec63a03732cff30f99f8df94b78709455e48d2c9309136b44630f793`.
Raw text is not committed.

The CFPB states that narratives are unverified and reflect one side of a
dispute. They are therefore inappropriate for ranking companies or asserting
that alleged events occurred. Since complaints are overwhelmingly negative,
this corpus trains the aspect model—not the overall sentiment model.

```bash
insightpulse-fetch-cfpb \
  --output data/raw/cfpb/complaints.jsonl \
  --date-min 2019-01-01 --date-max 2020-01-01 --limit 1500 \
  --products "Credit card or prepaid card" "Checking or savings account" \
    "Mortgage" "Debt collection" "Student loan"

insightpulse-prepare-benchmark cfpb \
  --input data/raw/cfpb/complaints.jsonl \
  --output-dir artifacts/benchmarks/cfpb

insightpulse-baseline --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect-baseline --tasks aspect
```
