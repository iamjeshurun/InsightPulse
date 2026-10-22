# Part 4: Dashboard

The dashboard is a single page that shows what the aspect model does on real
complaints, then lets a visitor try it.

## What the page shows

- **A worked example.** `scripts/build_case_study.py` runs the bundled aspect
  model over archived January 2024 CFPB complaints and writes
  `frontend/public/example-insights.json`. The page loads that file, so it
  renders without waiting for the API. It shows agreement with CFPB's own
  categories, the 2019 test-set macro-F1 against the fine-tuned transformers,
  and how many disagreements a review of the least-confident labels catches.
- **Evidence for every label.** Each theme lists its F1 and sample complaints
  with the words that drove the label highlighted, weighted by the model.
- **Disagreements.** The most confident cases where the model and CFPB's
  category differ, which are often defensible because CFPB's labels are
  references, not ground truth.
- **Live analysis.** Text a visitor submits goes to the hosted API. The result
  shows the theme, its confidence, the words behind it, the other task labels,
  and whether it falls below the 0.40 review threshold. A visitor can suggest a
  different theme, which is saved through the feedback endpoint.
- **API status.** The header polls `/health` and reports when the free-tier
  API is waking up, ready, or unavailable.

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

## Limitations

The page is unauthenticated. Submitted text and corrections are stored, but the
public deployment does not list them back through the API
(`INSIGHTPULSE_PUBLIC_RECORDS=false`), and Render's ephemeral disk erases them
on every redeploy. A shared deployment would need accounts and per-user access
before stored analyses could be shown to anyone.
