# Reproducible baseline benchmark

Run date: 2026-09-07. Seed 42, scikit-learn 1.9.0, Python 3.13. Latency is
measured on the training machine (Apple M5).

| Task | Classes | Train / validation / test | Accuracy | Macro-F1 | Mean latency per example |
| --- | ---: | ---: | ---: | ---: | ---: |
| DynaSent sentiment | 3 | 13,065 / 720 / 720 | 0.5847 | 0.5831 | 0.0073 ms |
| Bitext support intent | 27 | 19,040 / 2,365 / 2,397 | 0.9883 | 0.9873 | 0.0096 ms |
| CFPB aspect | 8 | 6,491 / 789 / 843 | 0.7224 | 0.6419 | 0.0830 ms |

Split sizes shift by a handful of records between runs because CFPB keeps
revising historical complaints and the Bitext regrouped split drops
exact-normalized duplicates; the numbers above are one such run and rebuild
within noise from the commands in `docs/datasets.md`.

## Interpretation

The sentiment result establishes the intended classical lower bound. DynaSent
Round 2 deliberately contains difficult examples. Error inspection shows the
bag-of-words baseline struggles with sarcasm, double negation, implicit
sentiment, and phrases whose meaning depends on context. For example, the
positive sentence “I would never not recommend this place” was confidently
misclassified as negative. This is a concrete motivation for the transformer
experiment.

The intent result is strong but must be read in context. Bitext is hybrid
synthetic, its classes use recognizable vocabulary, and both training and test
sets come from the same generation process. The split is now grouped by a
de-templated request key, which removed ~10% train/test instruction leakage and
moved macro-F1 only from 0.9910 to 0.9873 — the task is just close to solved for
a bag-of-words model at this distribution. It demonstrates the pipeline learns
and serves a 27-class problem; it is not evidence of real-world generalization.

The aspect baseline uses every CFPB complaint with a public narrative whose
`date_received` falls in January 2019: 8,911 narratives, 8,124 after exact
deduplication. The compact aspect label is deterministically derived from the
consumer-selected CFPB issue, sub-issue, and product fields — not inferred by a
model. Minority classes (`fees_interest`, `fraud_security`, `account_access`)
are where a stronger model has room to help.

## Transformer experiment

The transformer runner supports dynamic padding, configurable sequence length /
learning rate / batch size, square-root inverse-frequency class weights,
validation-based checkpoint selection, and the same held-out evaluation
contract as the baseline. Three candidates have been trained on the frozen CFPB
aspect splits; **all three lost to the classical baseline and none was
promoted.**

| Model | max_len | epochs | Test acc | Test macro-F1 | vs. baseline 0.642 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `google/bert_uncased_L-2_H-128_A-2` | 128 | 10 | 0.679 | 0.561 | −0.081 |
| `microsoft/deberta-v3-small` | 64 | 4 | 0.664 | 0.549 | −0.093 |
| `microsoft/deberta-v3-small` (class-weighted) | 256 | 4 | 0.684 | **0.564** | −0.078 |

The 256-token DeBERTa run (2e-5 LR, batch 16, Apple M5 GPU, ~38 min) climbed
0.469 → 0.564 → 0.591 → *(best checkpoint)* on validation macro-F1 but still
finished below the baseline on the held-out test set, and **worse on exactly
the minority classes it was meant to help**: `fraud_security` F1 fell from 0.455
to 0.188, `account_access` from 0.581 to 0.483.

| class | baseline F1 | DeBERTa-256 F1 | test n |
| --- | ---: | ---: | ---: |
| account_access | 0.581 | 0.483 | 53 |
| credit_reporting | 0.864 | 0.869 | 299 |
| debt_collection | 0.789 | 0.754 | 140 |
| fees_interest | 0.500 | 0.455 | 37 |
| fraud_security | 0.455 | 0.188 | 44 |
| loan_servicing | 0.657 | 0.615 | 96 |
| other | 0.711 | 0.628 | 65 |
| payments | 0.579 | 0.520 | 109 |

**Interpretation.** The aspect labels are weak supervision keyed off terms in
the CFPB `issue` field, and those terms recur almost verbatim in the narratives
— signal a linear TF-IDF model consumes directly. Contextual embeddings add
little here, and with only 37–53 training-equivalent examples in the rare
classes the fine-tune overfits the majority. The one thing DeBERTa did better:
calibration (ECE 0.084 vs the baseline's 0.226).

**Promotion rule (unchanged).** Promote a transformer only when it beats the
frozen-test macro-F1 *and* improves minority-class recall at acceptable latency
and memory. None of the three candidates qualifies, so the classical model is
served in production. The full DeBERTa-256 report is at
`artifacts/reports/cfpb-aspect-deberta-eval.json` after a rebuild; weights are
not committed.

A productive next step is better labels (a small hand-annotated aspect test set,
or aspect *spans* rather than issue-field groupings), not a bigger encoder.

## Reproduce

Follow `docs/datasets.md` to build the three benchmarks, then:

```bash
insightpulse-baseline --data-dir artifacts/benchmarks/dynasent \
  --output-dir artifacts/models/dynasent-baseline --tasks sentiment
insightpulse-baseline --data-dir artifacts/benchmarks/bitext \
  --output-dir artifacts/models/bitext-baseline --tasks intent
insightpulse-baseline --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect-baseline --tasks aspect

# the rejected transformer candidate (needs the [transformer] extra + a GPU)
insightpulse-transformer --data-dir artifacts/benchmarks/cfpb \
  --output-dir artifacts/models/cfpb-aspect-deberta --task aspect \
  --config configs/transformer.example.json
```

Generated reports include per-class precision/recall/F1, confusion matrices,
expected calibration error, behavior slices, error examples, model files, and
run configurations. Generated artifacts are Git-ignored; rebuild them from the
documented sources.
