# Part 3: Production Inference Platform

The FastAPI service turns the Part 2 model contract into a versioned application
interface. It supports real-time and batch inference, durable SQLite storage,
background jobs, analytics, human feedback, request IDs, CORS, rate limiting,
and short-lived analytics caching.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
insightpulse-api
```

Open `http://localhost:8000/docs` for the generated OpenAPI interface.

To load a trained Part 2 baseline:

```bash
export INSIGHTPULSE_MODEL_PATH=artifacts/models/baseline/baseline.joblib
export INSIGHTPULSE_DB=artifacts/insightpulse.db
insightpulse-api
```

Without a model artifact the API clearly identifies itself as
`demo-lexicon-1`. This keeps the product demonstrable without pretending the
fallback is a trained model.

## Endpoints

- `POST /api/v1/analyze`
- `POST /api/v1/analyze/batch`
- `POST /api/v1/jobs` and `GET /api/v1/jobs/{id}`
- `GET /api/v1/analyses` and `GET /api/v1/analyses/{id}`
- `GET /api/v1/analytics/summary`
- `POST /api/v1/feedback`
- `GET /health`

## Production migration notes

SQLite is deliberate for a free local portfolio deployment. The repository
boundary allows a later PostgreSQL adapter without changing API contracts.
Before internet-scale deployment, replace in-process jobs, caching, and rate
limits with Redis-backed workers and shared counters; add authentication,
tenant isolation, database migrations, encrypted backups, and secret management.
