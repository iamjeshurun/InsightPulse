# Operations Runbook

## Start and verify

```bash
docker compose up --build -d
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
```

Start the optional monitoring stack with
`docker compose --profile observability up --build -d`. Grafana is available
at `http://localhost:3000` and Prometheus at `http://localhost:9090`.

## Service incident

1. Check `/ready`, container health, and recent structured logs.
2. Inspect request error rate and latency in the operations dashboard.
3. Confirm disk capacity and write access for the database volume.
4. Stop ingestion if errors risk corrupting or losing feedback.
5. Restore the last verified container image and database backup.
6. Record the timeline, customer impact, cause, and preventive action.

## Model-quality incident

1. Preserve input, model-version, prediction, confidence, and correction data.
2. Compare label distributions and text-length/source/product drift.
3. Slice errors by task, class, source, product, and confidence.
4. If a candidate exists, deploy it as `INSIGHTPULSE_SHADOW_MODEL_PATH` first.
5. Promote only after offline gates and shadow disagreement review pass.

## Rollback

Container releases should be tagged with the Git commit. Re-deploy the previous
known-good tag; do not overwrite tags. Model artifacts must be immutable and
versioned separately from application code. After rollback, verify `/ready`,
run a known prediction, and confirm database writes and metrics.

## Backup and privacy

Back up the SQLite volume before releases and test restoration quarterly. Keep
raw customer data and backups encrypted with restricted access. Never upload
production feedback to CI artifacts without redaction and retention controls.
