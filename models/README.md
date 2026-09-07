# Bundled demo models

These are the trained classical baselines the public demo serves. They are
committed (≈3 MB total) so `docker compose up` and the Render deploy work out of
the box; they are **not** the source of truth — rebuild them anytime with:

```bash
# sentiment
insightpulse-prepare-benchmark dynasent --input data/raw/dynasent/dynasent-v1.1.zip \
  --output-dir artifacts/benchmarks/dynasent
insightpulse-baseline --data-dir artifacts/benchmarks/dynasent \
  --output-dir artifacts/models/dynasent --tasks sentiment
cp artifacts/models/dynasent/baseline.joblib models/dynasent-sentiment.joblib

# aspect
insightpulse-fetch-cfpb --output data/raw/cfpb/complaints-2019-01.jsonl \
  --date-min 2019-01-01 --date-max 2019-02-01 --limit 20000
insightpulse-prepare-benchmark cfpb --input data/raw/cfpb/complaints-2019-01.jsonl \
  --output-dir artifacts/benchmarks/cfpb
insightpulse-baseline --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect --tasks aspect
cp artifacts/models/cfpb-aspect/baseline.joblib models/cfpb-aspect.joblib
```

| File | Task | Data | Test macro-F1 | Notes |
| --- | --- | --- | ---: | --- |
| `dynasent-sentiment.joblib` | sentiment | DynaSent v1.1 R2 | 0.583 | review-domain; transfers only roughly to other text |
| `cfpb-aspect.joblib` | aspect (8-class) | CFPB Jan 2019 complaints | 0.642 | financial-complaint domain |

`intent` and `urgency` have no licensed training set that matches the platform's
taxonomy, so the demo serves them from the transparent rule-based lexicon.
`GET /health` always reports which is which.

Built with scikit-learn 1.9, Python 3.13. Pickled sklearn estimators are
version-sensitive; the runtime pins a compatible range in `pyproject.toml`.
