# Portfolio notes (résumé bullets & talking points)

Every claim here traces to a command in this repo. Numbers are held-out
test-set results, not targets. `<...>` placeholders get filled once the demo is
deployed and the final transformer run lands.

## Résumé bullets

**Compact (3 lines):**

- Built **InsightPulse**, an end-to-end voice-of-customer ML platform: a
  reproducible data pipeline (PII redaction, dedup, deterministic
  leakage-safe splits), classical + transformer modeling with a shared
  evaluation contract, a versioned FastAPI service, a React decision
  dashboard, and Docker/CI/Prometheus operations — 28 automated tests.
- Trained and evaluated an 8-class aspect classifier on 8k real CFPB consumer
  complaint narratives: a TF-IDF + logistic-regression baseline at **0.642
  macro-F1** beat three fine-tuned transformers (BERT-tiny, DeBERTa-v3-small at
  64 and 256 tokens; best 0.564) under a written promotion rule — the label
  signal is lexical, so the linear model consumes it directly.
- Shipped a monitored inference service — batch + real-time endpoints,
  background jobs, PSI/Jensen-Shannon drift detection, calibration (ECE)
  tracking, and a human-correction feedback loop feeding continuous evaluation;
  ~900 req/s at 12 ms p95 in local load tests; deployed a public demo at
  `<DEMO_URL>`.

**Single line:**

- Built and deployed InsightPulse, a voice-of-customer ML platform (reproducible
  data pipeline → baseline + fine-tuned transformer → FastAPI + React →
  Docker/CI/Prometheus): 8-class aspect classification at 0.642 macro-F1 on 8k
  real complaint narratives, drift + calibration monitoring, human-in-the-loop
  correction, 28 tests, live demo.

## Measured facts to quote

| Metric | Value | Where |
| --- | --- | --- |
| Sentiment macro-F1 (DynaSent R2, 720 test) | 0.583 | `artifacts/models/dynasent-baseline` |
| Aspect macro-F1, TF-IDF (CFPB, 843 test, 8-class) | 0.642 | `artifacts/models/cfpb-aspect-baseline` |
| Aspect macro-F1, DeBERTa-v3-small (rejected) | 0.564 | `docs/benchmark-results.md` |
| Support-intent macro-F1 (Bitext, 2,397 test, 27-class) | 0.987 | `artifacts/models/bitext-baseline` |
| Aspect baseline inference latency | ~0.08 ms/example | evaluation report |
| API load test (1,000 req, concurrency 10, M5, SQLite write/req) | ~900 req/s, p95 ~12 ms, 0 errors | `scripts/load_test.py` |
| Automated tests | 28 (25 backend + 3 frontend) | `tests/`, `frontend/src` |

## Story points (for interviews)

- **Reproducibility over headline numbers.** The prior version quoted an aspect
  benchmark that couldn't be rebuilt from the repo — the CFPB fetcher was
  silently capped at ~2k rows by a dead `frm` pagination parameter. Rewrote it
  to use the API's `search_after` cursor; the benchmark now rebuilds from one
  documented command.
- **Found and fixed train/test leakage.** ~10% of the Bitext intent test set
  shared a de-templated instruction with train. Regrouped the split by request
  key; documented that the score still isn't production evidence because the
  data is same-generator synthetic.
- **Honest negative results.** Three fine-tuned transformers (BERT-tiny,
  DeBERTa-v3-small at 64 and 256 tokens) all lost to the classical baseline and
  were rejected, not buried — DeBERTa was actually *worse* on the minority
  classes it was meant to help. The promotion rule is written in
  `docs/part-2-modeling.md`.
- **Calibration matters for the product.** The aspect baseline's ECE is ~0.23
  (over-confident); the dashboard's 65%-confidence review queue is the
  mitigation, and continuous-eval watches agreement with human corrections.
- **Domain honesty.** The three benchmarks are three domains; the README says
  so, and `/health` reports which tasks use a trained model vs. the lexicon.

## What's deliberately still open

Aspect-level *sentiment* (a polarity per aspect), auth/multi-tenancy, Postgres +
a real job queue, and an organic (non-synthetic) intent benchmark. These are
scoped in the `docs/part-*.md` limitation sections — name them before a
reviewer does.
