# InsightPulse

InsightPulse is an end-to-end **voice-of-customer intelligence platform**: it
takes raw customer feedback — reviews, surveys, support tickets, complaint
narratives — and turns it into structured, reviewable signal that a product or
support team can act on. It is built as a portfolio project to show the full
applied-ML lifecycle, from a reproducible dataset to a monitored service.

<!-- DEMO -->
<!-- Live demo: <DEMO_URL> -->

## The problem

"Is this review positive or negative?" is not a useful question on its own. A
team drowning in feedback needs to know:

- **How does the customer feel?** (sentiment)
- **What are they talking about?** (aspect — billing, account access, fraud, fees, …)
- **How urgent is it?** (triage)
- **Which predictions should a human check?** (a low-confidence review queue)
- **Is the model still trustworthy?** (drift and calibration monitoring)

InsightPulse answers those questions behind one API and one dashboard, and it
keeps the human in the loop: every prediction can be corrected, and corrections
accumulate into an evaluation set.

## Architecture

```text
             ┌──────────────┐     ┌───────────────────────────┐
feedback ──▶ │ data pipeline│ ──▶ │ benchmarks (JSONL splits) │
             │ validate ·   │     └──────────────┬────────────┘
             │ redact PII · │                    │
             │ dedupe ·     │        ┌───────────▼───────────┐
             │ split        │        │ modeling              │
             └──────────────┘        │ TF-IDF baseline  ──┐  │
                                     │ DeBERTa fine-tune ─┴▶ evaluation
                                     └───────────┬───────────┘   · macro-F1
                                                 │               · calibration
                    ┌────────────────────────────▼──┐            · error slices
   React dashboard ▶│ FastAPI  /api/v1              │            · latency
   · KPIs & charts  │  analyze · batch · jobs       │
   · evidence table │  analytics · feedback         │──▶ SQLite (analyses,
   · review queue   │  /health /ready /metrics      │        jobs, corrections)
   · corrections    └───────────────┬───────────────┘
                                    │
              Prometheus ◀── /metrics ──▶ drift & continuous-eval jobs
                    │
                 Grafana                 GitHub Actions: tests · build · image
```

Five layers, each independently runnable, connected by stable contracts:

| Layer | What it does | Docs |
| --- | --- | --- |
| 1 · Data | schema validation, PII redaction, dedupe, deterministic splits, dataset cards | [part 1](docs/part-1-data-foundation.md) |
| 2 · Modeling | classical baseline + optional transformer, one evaluation contract | [part 2](docs/part-2-modeling.md) · [datasets](docs/datasets.md) |
| 3 · API | versioned FastAPI: real-time & batch inference, jobs, analytics, feedback | [part 3](docs/part-3-inference-platform.md) |
| 4 · Dashboard | React decision surface: KPIs, distributions, evidence, review queue | [part 4](docs/part-4-dashboard.md) |
| 5 · Operations | Docker, CI, Prometheus/Grafana, drift, continuous evaluation, runbook | [part 5](docs/part-5-operations.md) · [architecture](docs/architecture.md) |

## Measured results

Every number below is a held-out **test-set** measurement from a command in
this repo — not a target. Reproduce them with [docs/datasets.md](docs/datasets.md)
then [docs/benchmark-results.md](docs/benchmark-results.md).

| Task | Dataset (license) | Train / test | Model | Accuracy | Macro-F1 |
| --- | --- | ---: | --- | ---: | ---: |
| Sentiment | DynaSent v1.1 R2 (CC BY 4.0) | 13,065 / 720 | TF-IDF + logistic regression | 0.585 | **0.583** |
| Aspect (8-class) | CFPB complaints, Jan 2019 (CC0) | 6,491 / 843 | TF-IDF + logistic regression | 0.722 | **0.642** |
| Aspect (8-class) | same splits | 6,491 / 843 | DeBERTa-v3-small, fine-tuned | `<DEBERTA_ACC>` | `<DEBERTA_F1>` |
| Support intent (27-class) | Bitext v11 (CDLA-Sharing 1.0) | 19,040 / 2,397 | TF-IDF + logistic regression | 0.988 | 0.987 |

**Reading these honestly:**

- The **sentiment** baseline is a deliberate classical lower bound. DynaSent R2
  is adversarially hard; the bag-of-words model fails on negation, sarcasm, and
  implicit sentiment (e.g. it calls *"I would never not recommend this place"*
  negative).
- The **aspect** task uses real consumer complaint language. Labels are
  deterministic groupings of the consumer-selected CFPB `issue`/`sub-issue`
  fields (traceable weak supervision, not model-generated). Minority classes
  (`fees_interest`, `fraud_security`) are where a transformer has room to help.
- The **27-class intent** score is high because Bitext is hybrid-synthetic and
  train/test come from the same generator. The split is grouped by de-templated
  request key so no instruction leaks across it, but this is evidence the
  *pipeline* scales to many classes — **not** evidence of production accuracy on
  organic tickets.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
python -m unittest discover -s tests -v          # 22 backend tests

# API + dashboard (rule-based demo model until you train one)
( cd frontend && npm ci && npm run build )
insightpulse-api                                  # http://localhost:8000  ·  /docs

# or the whole thing in Docker
docker compose up --build
docker compose --profile observability up --build # + Prometheus :9090 / Grafana :3000
```

Train and serve real models:

```bash
# 1. build a benchmark (downloads public data at build time, nothing raw is committed)
insightpulse-fetch-cfpb --output data/raw/cfpb/complaints-2019-01.jsonl \
  --date-min 2019-01-01 --date-max 2019-02-01 --limit 20000
insightpulse-prepare-benchmark cfpb --input data/raw/cfpb/complaints-2019-01.jsonl \
  --output-dir artifacts/benchmarks/cfpb

# 2. train + evaluate the classical baseline
insightpulse-baseline --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect --tasks aspect

# 3. point the API at it
export INSIGHTPULSE_ASPECT_MODEL_PATH=artifacts/models/cfpb-aspect/baseline.joblib
insightpulse-api
```

`GET /health` reports exactly which tasks are served by a trained model and
which fall back to the transparent lexicon.

## Input contract

CSV or JSONL. Required: `id`, `text` (3–10,000 chars), `source`
(`review` / `survey` / `support_ticket`), `product`, `created_at` (ISO-8601).
Optional labels: `sentiment`, `intent`, `urgency`, `aspect`. See
[docs/annotation_guidelines.md](docs/annotation_guidelines.md).

## Privacy & responsible use

- Regex redaction covers emails, phones, IPv4, card-like numbers, and common
  account identifiers. It is defense-in-depth, **not** a guarantee — production
  data still needs access control and human review.
- CFPB narratives are unverified allegations and one side of a dispute; they
  must not be used to rank companies or assert that events occurred, and the
  corpus is too negative to train general sentiment.
- Predictions are decision *support*. Nothing here should drive automated
  credit, employment, legal, or safety decisions.

## Known limitations

See each `docs/part-*.md` for the full list. The largest: the three benchmarks
are different domains; aspect-level *sentiment* (a sentiment per aspect) is not
yet implemented; SQLite, in-process jobs, and the in-memory rate limiter suit a
single instance, not scale; there is no authentication.

## License

Code and docs: MIT (see [LICENSE](LICENSE)). Dataset licenses are the datasets'
own — see [docs/datasets.md](docs/datasets.md).
