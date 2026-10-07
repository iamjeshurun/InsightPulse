"""Evaluate the bundled aspect model on archived January 2024 CFPB complaints.

Produces the dashboard's precomputed example (frontend/public/example-insights.json)
and a written report (docs/case-study-2024.md). Every figure comes from the data
and models in this repository.

Inputs:
  data/raw/cfpb/archive-2024-01-01-to-04.jsonl   insightpulse-fetch-cfpb --date-min 2024-01-01 --date-max 2024-01-05
  artifacts/benchmarks/cfpb-2019-01/             the January 2019 benchmark splits
  data/case-study/previously-inspected-ids.txt   records excluded because they were inspected earlier

This is a case study, not a held-out test: the model's exact training file is no
longer available, so exclusion of these records from training is supported by
evidence (no ID or text overlap with any surviving split, no memorisation
signature) but not proven.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import joblib

from insightpulse_data.cfpb import classify_aspect
from insightpulse_data.privacy import redact_pii

ROOT = Path(__file__).resolve().parent.parent
SLICE = ROOT / "data" / "raw" / "cfpb" / "archive-2024-01-01-to-04.jsonl"
BENCHMARK_2019 = ROOT / "artifacts" / "benchmarks" / "cfpb-2019-01"
EXCLUDED_IDS = ROOT / "data" / "case-study" / "previously-inspected-ids.txt"
ASPECT_MODEL = ROOT / "models" / "cfpb-aspect.joblib"
SENTIMENT_MODEL = ROOT / "models" / "dynasent-sentiment.joblib"
EXAMPLE_OUT = ROOT / "frontend" / "public" / "example-insights.json"
REPORT_OUT = ROOT / "docs" / "case-study-2024.md"
GENERATED_AT = "2026-10-07"
EXCERPT_CHARS = 300


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Whole sentences up to `limit` characters, with CFPB's XXXX redactions collapsed."""
    text = re.sub(r"\{\$([\d,.]+)\}", r"$\1", text)
    text = re.sub(r"(?:X{2,}[ /\-]*)+", "[redacted] ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return (cut[: end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0]) + " …"


def evaluate(model, texts: list[str], labels: list[str]) -> dict:
    predictions = [p["aspect"] for p in model.predict(texts)]
    predicted = [p["label"] for p in predictions]
    confidence = [p["confidence"] for p in predictions]
    classes = sorted(set(labels) | set(predicted))
    counts = Counter(labels)
    per_class = {}
    for name in classes:
        tp = sum(p == a == name for p, a in zip(predicted, labels))
        predicted_n = sum(p == name for p in predicted)
        precision = tp / predicted_n if predicted_n else 0.0
        recall = tp / counts[name] if counts[name] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {
            "n": counts[name],
            "share": round(counts[name] / len(labels), 4),
            "predicted": predicted_n,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }
    accuracy = sum(p == a for p, a in zip(predicted, labels)) / len(labels)
    majority, majority_n = counts.most_common(1)[0]
    se = math.sqrt(accuracy * (1 - accuracy) / len(labels))
    return {
        "n": len(labels),
        "accuracy": round(accuracy, 3),
        "accuracy_95ci": [round(accuracy - 1.96 * se, 3), round(accuracy + 1.96 * se, 3)],
        "macro_f1": round(sum(c["f1"] for c in per_class.values() if c["n"]) / sum(1 for c in per_class.values() if c["n"]), 3),
        "majority_class": majority,
        "majority_baseline": round(majority_n / len(labels), 3),
        "per_class": per_class,
        "confusion": {a: {p: sum(1 for x, y in zip(labels, predicted) if x == a and y == p) for p in classes} for a in classes},
        "_predicted": predicted,
        "_confidence": confidence,
    }


def calibration(result: dict, labels: list[str]) -> dict:
    correct = [p == a for p, a in zip(result["_predicted"], labels)]
    bins, ece = [], 0.0
    for low in [i / 10 for i in range(10)]:
        members = [i for i, c in enumerate(result["_confidence"]) if low <= c < low + 0.1 or (low == 0.9 and c == 1.0)]
        if not members:
            continue
        acc = sum(correct[i] for i in members) / len(members)
        conf = sum(result["_confidence"][i] for i in members) / len(members)
        ece += len(members) / len(labels) * abs(acc - conf)
        bins.append({"range": [round(low, 1), round(low + 0.1, 1)], "n": len(members), "accuracy": round(acc, 3), "confidence": round(conf, 3)})
    return {"ece": round(ece, 3), "bins": bins}


def review_tradeoff(result: dict, labels: list[str], threshold: float) -> dict:
    correct = [p == a for p, a in zip(result["_predicted"], labels)]
    flagged = [c < threshold for c in result["_confidence"]]
    errors = sum(not c for c in correct)
    kept = [c for c, f in zip(correct, flagged) if not f]
    return {
        "threshold": threshold,
        "flagged_share": round(sum(flagged) / len(labels), 3),
        "errors_caught_share": round(sum(f and not c for f, c in zip(flagged, correct)) / errors, 3) if errors else 0.0,
        "accuracy_unflagged": round(sum(kept) / len(kept), 3) if kept else None,
        "unflagged_n": len(kept),
    }


def choose_threshold(result: dict, labels: list[str]) -> float:
    """Pick the threshold on validation data that maximises errors caught minus share flagged."""
    candidates = [round(0.2 + 0.025 * i, 3) for i in range(25)]
    return max(candidates, key=lambda t: (lambda r: r["errors_caught_share"] - r["flagged_share"])(review_tradeoff(result, labels, t)))


def public(result: dict) -> dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def main() -> None:
    aspect_model = joblib.load(ASPECT_MODEL)
    sentiment_model = joblib.load(SENTIMENT_MODEL)
    excluded = {line.strip() for line in EXCLUDED_IDS.read_text().splitlines() if line.strip() and not line.startswith("#")}
    slice_rows = read_jsonl(SLICE)
    slice_meta = json.loads(SLICE.with_suffix(SLICE.suffix + ".metadata.json").read_text())
    rows = [row for row in slice_rows if row["complaint_id"] not in excluded]
    texts = [redact_pii(row["narrative"])[0] for row in rows]
    labels = [classify_aspect(row["issue"], row.get("sub_issue", ""), row["product"]) for row in rows]

    validation = read_jsonl(BENCHMARK_2019 / "validation.jsonl")
    test = read_jsonl(BENCHMARK_2019 / "test.jsonl")
    val_labels, test_labels = [r["aspect"] for r in validation], [r["aspect"] for r in test]
    val_result = evaluate(aspect_model, [r["text"] for r in validation], val_labels)
    test_result = evaluate(aspect_model, [r["text"] for r in test], test_labels)
    case_result = evaluate(aspect_model, texts, labels)
    test_result["calibration"] = calibration(test_result, test_labels)
    case_result["calibration"] = calibration(case_result, labels)

    # Label rules unchanged: recomputing the stored 2019 labels with today's rules.
    rule_agreement = sum(
        classify_aspect(r["issue"], r.get("sub_issue", ""), r["product"]) == r["aspect"] for r in test
    ) / len(test)
    # How much of the gap is class mix: 2019 per-class recall applied to the 2024 class mix.
    mix_expected = sum(test_result["per_class"][c]["recall"] * v["share"] for c, v in case_result["per_class"].items() if c in test_result["per_class"])

    threshold = choose_threshold(val_result, val_labels)
    tradeoff = {
        "chosen_on": "2019 validation split",
        "rule": "maximise share of errors caught minus share flagged",
        "validation_2019": review_tradeoff(val_result, val_labels, threshold),
        "test_2019": review_tradeoff(test_result, test_labels, threshold),
        "case_2024": review_tradeoff(case_result, labels, threshold),
        "current_rule_0_65": {
            "test_2019": review_tradeoff(test_result, test_labels, 0.65),
            "case_2024": review_tradeoff(case_result, labels, 0.65),
        },
    }
    sentiment = Counter(p["sentiment"]["label"] for p in sentiment_model.predict(texts))

    by_product = {}
    for row, label, predicted in zip(rows, labels, case_result["_predicted"]):
        by_product.setdefault(row["product"], []).append(label == predicted)
    products = {name: {"n": len(v), "accuracy": round(sum(v) / len(v), 3)} for name, v in sorted(by_product.items(), key=lambda kv: -len(kv[1]))}

    full_text = {row["complaint_id"]: text for row, text in zip(rows, texts)}
    records = [
        {
            "id": row["complaint_id"],
            "date": row["date_received"],
            "product": row["product"],
            "issue": row["issue"],
            "cfpb_label": label,
            "model_label": predicted,
            "confidence": round(confidence, 3),
            "excerpt": excerpt(text),
        }
        for row, text, label, predicted, confidence in zip(rows, texts, labels, case_result["_predicted"], case_result["_confidence"])
    ]
    # Evidence: the most confident agreements per theme. Disagreements: the most
    # confident ones, one per (CFPB label, model label) pair, so the list is varied.
    evidence = {}
    for name in case_result["per_class"]:
        agreed = sorted((r for r in records if r["cfpb_label"] == r["model_label"] == name), key=lambda r: -r["confidence"])
        evidence[name] = agreed[:2]
    disagreements, seen_pairs = [], set()
    for record in sorted((r for r in records if r["cfpb_label"] != r["model_label"]), key=lambda r: -r["confidence"]):
        pair = (record["cfpb_label"], record["model_label"])
        if pair not in seen_pairs and len(record["excerpt"]) > 120:
            seen_pairs.add(pair)
            disagreements.append(record)
        if len(disagreements) == 6:
            break

    def with_terms(record: dict) -> dict:
        terms = aspect_model.top_terms(full_text[record["id"]], "aspect", record["model_label"])
        return {**record, "terms": [[term, score] for term, score in terms]}

    evidence = {name: [with_terms(r) for r in items] for name, items in evidence.items()}
    disagreements = [with_terms(r) for r in disagreements]

    test_public, case_public = public(test_result), public(case_result)
    example = {
        "kind": "example",
        "title": "Archived CFPB complaint narratives, January 1–4, 2024",
        "generated_at": GENERATED_AT,
        "model": {"name": "Theme (aspect) classifier", "family": "TF-IDF + logistic regression", "file": "models/cfpb-aspect.joblib", "trained_on": "CFPB complaints received January 2019"},
        "dataset": {
            "name": "CFPB Consumer Complaint Database narratives archive",
            "source": slice_meta["source"],
            "license": slice_meta["license"],
            "date_range": ["2024-01-01", "2024-01-04"],
            "archived_narratives": len(slice_rows),
            "excluded_previously_inspected": len(slice_rows) - len(rows),
            "examples": len(rows),
            "duplicates_removed": slice_meta["skipped_exact_duplicates"],
            "narrative_cutoff": slice_meta["narrative_cutoff"],
        },
        "evaluation_type": "case study, not a held-out test",
        "reference_labels": "CFPB categories derived from the issue each consumer selected. Useful reference labels, not infallible ground truth.",
        "results": {"2019_test": test_public, "2024_case": case_public, "class_mix_expected_accuracy": round(mix_expected, 3), "label_rules_unchanged": rule_agreement == 1.0},
        # Held-out 2019 transformer comparison, from docs/benchmark-results.md.
        "transformers_2019": {"best_macro_f1": 0.564, "models_tried": 3, "source": "docs/benchmark-results.md"},
        "products": products,
        "review": tradeoff,
        "evidence": evidence,
        "disagreements": disagreements,
        "excluded_claims": {
            "sentiment": "Not shown: the sentiment model was trained on general reviews, and on complaints it labelled "
            f"{sentiment.get('neutral', 0)} of {len(rows)} neutral and {sentiment.get('positive', 0)} positive.",
            "intent_urgency": "Not shown: these come from keyword rules with no reference labels to check them against.",
        },
    }
    EXAMPLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_OUT.write_text(json.dumps(example, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT_OUT.write_text(render_report(example, val_result, sentiment, rule_agreement), encoding="utf-8")
    print(f"{len(rows)} examples · 2019 test acc {test_result['accuracy']} · 2024 acc {case_result['accuracy']} · threshold {threshold}")


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(header))) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def render_report(example: dict, val_result: dict, sentiment: Counter, rule_agreement: float) -> str:
    t19, c24 = example["results"]["2019_test"], example["results"]["2024_case"]
    d = example["dataset"]
    review = example["review"]
    classes = sorted(set(t19["per_class"]) | set(c24["per_class"]))
    per_class_rows = [
        [c, t19["per_class"].get(c, {}).get("n", 0), f"{t19['per_class'].get(c, {}).get('precision', 0):.2f}", f"{t19['per_class'].get(c, {}).get('recall', 0):.2f}",
         c24["per_class"].get(c, {}).get("n", 0), f"{c24['per_class'].get(c, {}).get('precision', 0):.2f}", f"{c24['per_class'].get(c, {}).get('recall', 0):.2f}"]
        for c in classes
    ]
    confusion = [[a] + [c24["confusion"][a][p] for p in classes] for a in classes]
    review_rows = [
        [name, f"{r['threshold']:.3f}", f"{r['flagged_share']:.1%}", f"{r['errors_caught_share']:.1%}", r["accuracy_unflagged"]]
        for name, r in [("2019 validation (chosen here)", review["validation_2019"]), ("2019 test", review["test_2019"]), ("2024 case study", review["case_2024"]),
                        ("Old 0.65 rule, 2019 test", review["current_rule_0_65"]["test_2019"]), ("Old 0.65 rule, 2024", review["current_rule_0_65"]["case_2024"])]
    ]
    product_rows = [[name, v["n"], f"{v['accuracy']:.2f}"] for name, v in example["products"].items()]
    return f"""# Case study: archived January 2024 CFPB complaints

Generated by `scripts/build_case_study.py` on {example['generated_at']}. Regenerate with:

```bash
insightpulse-fetch-cfpb --output data/raw/cfpb/archive-2024-01-01-to-04.jsonl \\
  --date-min 2024-01-01 --date-max 2024-01-05 --limit 100000
python scripts/build_case_study.py
```

## Data

- **Source:** {d['name']} ({d['license']}). CFPB stopped publishing narratives on
  {d['narrative_cutoff']}; the archive holds every narrative published before then, and no newer
  narratives exist publicly.
- **Slice:** every archived narrative received January 1–4, 2024: {d['archived_narratives']:,} after removing
  {d['duplicates_removed']:,} exact duplicates (mostly template letters).
- **Excluded:** {d['excluded_previously_inspected']} records that were inspected in an earlier benchmark
  (`data/case-study/previously-inspected-ids.txt`). **{d['examples']:,} records remain.**
- **Reference labels:** {example['reference_labels']} The rules that derive them are unchanged since training
  (recomputing the stored 2019 test labels agrees {rule_agreement:.0%}).

## Why this is a case study, not a held-out test

The bundled model (`models/cfpb-aspect.joblib`) was trained on January 2019 complaints, but its exact
training file no longer exists, so exclusion cannot be proven. The evidence:

- No complaint-ID or normalised-text overlap with any surviving 2019 train, validation, or test split.
- No memorisation signature: the model scores 0.886 on 2019 training records, 0.72 on 2019 validation and
  test, and {c24['accuracy']:.2f} here.

## Results

| | 2019 held-out test | 2024 case study |
|---|---:|---:|
| Records | {t19['n']} | {c24['n']:,} |
| Accuracy (95% CI) | {t19['accuracy']:.3f} ({t19['accuracy_95ci'][0]:.2f}–{t19['accuracy_95ci'][1]:.2f}) | {c24['accuracy']:.3f} ({c24['accuracy_95ci'][0]:.2f}–{c24['accuracy_95ci'][1]:.2f}) |
| Macro-F1 | {t19['macro_f1']:.3f} | {c24['macro_f1']:.3f} |
| Majority-class baseline | {t19['majority_baseline']:.3f} ({t19['majority_class']}) | {c24['majority_baseline']:.3f} ({c24['majority_class']}) |

Applying the 2019 per-class recall to the 2024 class mix predicts an accuracy of
{example['results']['class_mix_expected_accuracy']:.3f}, against {c24['accuracy']:.3f} observed. Overall accuracy
mostly reflects how many complaints are about credit reporting (the easiest class), so compare classes rather
than the headline number. The majority-class baseline rises for the same reason, and macro-F1, which weights
every class equally, falls from {t19['macro_f1']:.3f} to {c24['macro_f1']:.3f}.

### Per class

{table(['Class', '2019 n', '2019 P', '2019 R', '2024 n', '2024 P', '2024 R'], per_class_rows)}

### Confusion matrix, 2024 (rows: CFPB label, columns: model)

{table(['CFPB label / model'] + classes, confusion)}

### Accuracy by product, 2024

{table(['Product', 'n', 'Accuracy'], product_rows)}

## Confidence and review

The model is under-confident: on the 2019 test set its expected calibration error is
{calibration_value(t19)}. Low confidence alone is therefore not evidence of drift.

A review threshold was chosen on the 2019 validation split by maximising the share of errors caught minus
the share of records flagged, then applied unchanged:

{table(['Data', 'Threshold', 'Flagged', 'Errors caught', 'Accuracy of the rest'], review_rows)}

The previous 0.65 rule flags most records, so it is not a useful triage rule.

## What is not claimed

- **Sentiment:** the sentiment model was trained on general product reviews. On these complaints it predicted
  {dict(sentiment)}, which mislabels complaints as neutral or positive, so the example shows no sentiment results.
- **Intent and urgency:** keyword rules with no reference labels; not evaluated.
- **Trends:** four days of data cannot support a time trend.
"""


def calibration_value(result: dict) -> str:
    return f"{result['calibration']['ece']:.3f}" if "calibration" in result else "see below"


if __name__ == "__main__":
    main()
