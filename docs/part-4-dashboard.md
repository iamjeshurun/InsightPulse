# Part 4: Decision Dashboard

The React dashboard turns model output into an operational review surface. It
is designed around decisions—not decorative model demos—and works against the
versioned Part 3 API.

## Capabilities

- Overall volume, negative-rate, confidence, and review-queue KPIs
- Sentiment and intent distributions
- Real-time text analysis with product and source context
- CSV batch upload with quoted-field parsing and a 100-record safety limit
- Evidence table with signal filters and explicit confidence
- Human correction workflow persisted through the feedback API
- Low-confidence review queue
- CSV export for downstream analysis
- Responsive desktop and mobile layouts
- Visible API and model health state

## Run in development

Terminal one:

```bash
source .venv/bin/activate
insightpulse-api
```

Terminal two:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Production build

```bash
cd frontend
npm ci
npm run test
npm run build
cd ..
insightpulse-api
```

When `frontend/dist` exists, FastAPI serves the compiled single-page dashboard
at `/` while API routes remain under `/api/v1`.

## Product limitations

The current dashboard is single-user and unauthenticated for local portfolio
use. A shared deployment requires authentication, tenant isolation, role-based
access, accessible correction taxonomies, pagination, audit logs, and stronger
CSV validation. Part 5 adds packaging and operational visibility.
