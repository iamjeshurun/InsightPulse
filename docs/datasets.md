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
