# Deployment

InsightPulse ships as one container (multi-stage: Node builds the dashboard,
Python serves API + static files). It reads `$PORT` and health-checks `/ready`,
so it runs on any container host.

## Free-tier public demo (Render)

1. Push this repo to GitHub.
2. render.com → **New → Blueprint** → pick the repo. `render.yaml` provisions a
   free Docker web service.
3. After the first deploy, set `INSIGHTPULSE_CORS_ORIGINS` to the assigned
   `https://<name>.onrender.com` origin and redeploy.

Free-tier facts to expect (and to state on a résumé honestly):

- The instance **sleeps after ~15 min idle**; the first request afterwards
  takes a few seconds to wake.
- The disk is **ephemeral** — the SQLite history resets on every deploy. Fine
  for a demo; the analytics simply start from zero again.
- 512 MB RAM. The classical models fit comfortably; this is why the image does
  **not** include PyTorch.

## Serving trained models

The image bundles the classical baselines in `models/` and points
`INSIGHTPULSE_SENTIMENT_MODEL_PATH` / `INSIGHTPULSE_ASPECT_MODEL_PATH` at them
by default (see `Dockerfile`). `GET /health` returns the exact per-task model
version so it is always clear what is trained and what is the lexicon fallback.

To serve a fine-tuned transformer instead, host it behind a separate service
with the `[transformer]` extra installed and set `INSIGHTPULSE_ASPECT_MODEL_PATH`
to that endpoint — kept out of the default image to protect the 512 MB budget.

## Upgrade path for a real deployment

| Concern | Local / demo | Production |
| --- | --- | --- |
| Database | SQLite file | PostgreSQL via the `Repository` seam |
| Jobs | in-process `BackgroundTasks` | Redis + a worker (Celery / Dramatiq) |
| Rate limit / cache | in-memory | Redis or an API gateway |
| Auth | none | OIDC + tenant isolation + RBAC |
| Model artifacts | committed / baked | model registry, immutable versions |
| Secrets | `.env` (git-ignored) | host secret manager |

## Rollback

Tag every image with the Git commit. Redeploy the previous tag; never overwrite
tags. Model artifacts are versioned separately from code. After rollback verify
`/ready`, run a known prediction, confirm writes and `/metrics`. Full procedure
in [runbook.md](runbook.md).
