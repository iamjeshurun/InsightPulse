# Architecture

```text
Customer feedback -> React dashboard -> FastAPI v1 -> Model service
                              |              |            |-- primary model
                              |              |            `-- shadow model
                              |              |
                              |              `-> SQLite repository -> corrections
                              |
                              `-> analytics and review queue

FastAPI /metrics -> Prometheus -> Grafana
Processed data -> drift report -> evaluation gate -> retraining decision
Git push -> GitHub Actions -> tests -> frontend build -> container build
```

The local-first deployment uses one container and a persistent volume. The
interfaces—repository, model service, metrics endpoint, and versioned API—are
the seams for replacing SQLite with PostgreSQL, background tasks with a queue,
and local artifacts with object storage when scale warrants the complexity.
