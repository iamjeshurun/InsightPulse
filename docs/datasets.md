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
- Split: deterministic 80/10/10 grouped by a de-templated request key. Bitext
  reuses each request many times with only a `{{placeholder}}` or light
  phrasing change; grouping on the key (placeholders and punctuation removed)
  keeps every variant of one request in a single split and drops
  exact-normalized duplicates, so no instruction leaks from train into test.
  Even so, train and test come from the same generator and share vocabulary and
  structure, which is why the intent score is not evidence of production
  performance.

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
- Sampling: fixed dates, ascending created-date order, `search_after` cursor
  pagination (the API caps `frm` offsets at one page), exact narrative
  deduplication during collection. With no product filter the collector walks
  the entire date window; product filters switch it to round-robin.

The measured baseline is every complaint with a public narrative whose
`date_received` falls in January 2019 — 8,911 narratives, 8,124 after exact
deduplication. Because CFPB keeps revising historical records, the fetched file
is checksummed at build time (`<output>.metadata.json`) rather than pinned to a
number here; re-running the command below reproduces the splits within a few
records. Raw text is not committed.

The CFPB states that narratives are unverified and reflect one side of a
dispute. They are therefore inappropriate for ranking companies or asserting
that alleged events occurred. Since complaints are overwhelmingly negative,
this corpus trains the aspect model—not the overall sentiment model.

```bash
insightpulse-fetch-cfpb \
  --output data/raw/cfpb/complaints-2019-01.jsonl \
  --date-min 2019-01-01 --date-max 2019-02-01 --limit 20000

insightpulse-prepare-benchmark cfpb \
  --input data/raw/cfpb/complaints-2019-01.jsonl \
  --output-dir artifacts/benchmarks/cfpb

insightpulse-baseline --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect-baseline --tasks aspect
```
