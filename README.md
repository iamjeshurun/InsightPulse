# InsightPulse

InsightPulse is a portfolio-grade voice-of-customer intelligence platform. It
turns reviews, surveys, and support conversations into measurable product
insights while demonstrating an end-to-end applied machine-learning workflow.

## Roadmap

1. **Data foundation (complete):** validate, normalize, redact, deduplicate,
   split, and document customer-feedback data.
2. **Modeling:** establish classical baselines, fine-tune a transformer, and
   publish reproducible evaluation and error analysis.
3. **Inference platform:** expose versioned batch and real-time predictions via
   FastAPI with persistence, jobs, caching, and tests.
4. **Decision dashboard:** surface trends, aspects, alerts, evidence, and a
   human-feedback workflow.
5. **Operations:** containerize, deploy, monitor drift and service health, and
   automate continuous evaluation.

## Part 1 quick start

Requires Python 3.11 or newer and has no runtime dependencies.

```bash
python -m insightpulse_data.cli \
  --input data/sample_feedback.csv \
  --output-dir artifacts/processed \
  --dataset-name sample-feedback \
  --dataset-version 1.0.0

python -m unittest discover -s tests -v
```

The pipeline writes:

- `train.jsonl`, `validation.jsonl`, and `test.jsonl`
- `quarantine.jsonl` for invalid records
- `quality_report.json` with validation and class-distribution statistics
- `dataset_card.md` documenting provenance, transformations, and limitations
- `manifest.json` containing version information and SHA-256 checksums

All outputs are deterministic for the same input, seed, and configuration.
Raw customer text should be treated as sensitive and is excluded from Git.

## Expected input

CSV and JSONL inputs are supported. Each record must contain:

| Field | Required | Description |
| --- | --- | --- |
| `id` | yes | Stable record identifier |
| `text` | yes | Customer feedback, 3–10,000 characters |
| `source` | yes | `review`, `survey`, or `support_ticket` |
| `product` | yes | Product or service name |
| `created_at` | yes | ISO-8601 date or timestamp |
| `sentiment` | no | `positive`, `neutral`, or `negative` |
| `intent` | no | `praise`, `complaint`, `feature_request`, `churn_risk`, or `other` |
| `urgency` | no | `low`, `medium`, or `high` |

See [docs/annotation_guidelines.md](docs/annotation_guidelines.md) and
[docs/part-1-data-foundation.md](docs/part-1-data-foundation.md).

## Privacy

The pipeline redacts email addresses, phone numbers, IPv4 addresses, payment
card-like numbers, and common customer/account identifiers before data leaves
the processing stage. Regex redaction is defense-in-depth, not a guarantee;
production datasets still require access controls and human review.

## License

MIT
