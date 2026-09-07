# Part 5: Deployment and Continuous Improvement

Part 5 packages the complete product in a non-root, health-checked multi-stage
container and adds a reproducible local observability stack. No paid service is
required.

## Included controls

- Multi-stage frontend and API Docker build
- Docker Compose persistence and optional Prometheus/Grafana profile
- Liveness, readiness, request, prediction, confidence, and shadow metrics
- Pre-provisioned operations dashboard
- CI across Python 3.11/3.12, frontend tests/build, and container build
- Drift detection using PSI and Jensen-Shannon divergence
- Continuous evaluation against human corrections
- Shadow-model disagreement monitoring
- Concurrent HTTP load-test script
- Architecture, incident, backup, promotion, and rollback documentation

## Drift check

```bash
insightpulse-drift --reference artifacts/processed/train.jsonl \
  --current artifacts/current.jsonl --output artifacts/reports/drift.json \
  --fail-on-drift
```

## Feedback evaluation

```bash
insightpulse-evaluate-feedback --database artifacts/insightpulse.db \
  --output artifacts/reports/feedback-evaluation.json \
  --minimum-examples 30 --minimum-agreement 0.70
```

These gates produce evidence for a retraining decision; they do not retrain or
promote a model automatically. Human review remains required when data quality,
privacy, or business impact is uncertain.

## Load test

```bash
INSIGHTPULSE_RATE_LIMIT_PER_MINUTE=0 insightpulse-api &   # disable the limiter
python scripts/load_test.py --requests 1000 --concurrency 10
```

Reference run (Apple M5, one Uvicorn process, TF-IDF models, a SQLite write per
request): **0 errors**, ~900 req/s, p50 10 ms, p95 12 ms at concurrency 10;
p95 rises to ~32 ms at concurrency 25 and ~76 ms at 50 as the single worker and
the GIL saturate. Scaling past that means multiple workers and Postgres — see
[deployment.md](deployment.md).
