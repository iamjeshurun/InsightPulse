# Part 2: Modeling and Evaluation

## Experiment design

Part 2 establishes a classical lower bound before spending GPU time on a
transformer. Each task receives an independent TF-IDF and class-balanced
logistic-regression pipeline. This makes coefficients inspectable, inference
fast, and failure analysis straightforward.

The optional transformer entry point fine-tunes `distilroberta-base` one task
at a time and selects checkpoints using validation macro-F1. It is intentionally
not run against the ten-row demonstration dataset: such a result would be
statistically meaningless. Use a licensed, domain-appropriate dataset with
enough examples per class before claiming model quality.

## Reproduce the baseline

```bash
python -m insightpulse_data.cli \
  --input data/sample_feedback.csv \
  --output-dir artifacts/processed \
  --dataset-name sample-feedback \
  --dataset-version 1.0.0 \
  --train-ratio 0.6 \
  --validation-ratio 0.2

python -m insightpulse_modeling.cli \
  --data-dir artifacts/processed \
  --output-dir artifacts/models/baseline
```

## Fine-tune a transformer

```bash
pip install -e '.[transformer]'

python -m insightpulse_modeling.transformer \
  --data-dir artifacts/processed \
  --output-dir artifacts/models/sentiment-transformer \
  --task sentiment \
  --model-name distilroberta-base
```

## Evaluation contract

Every baseline run records:

- Accuracy, macro-F1, and weighted-F1
- Per-class precision, recall, F1, and support
- Confusion matrices with an explicit label order
- Expected calibration error
- Behavioral slices for negation, questions, and text length
- Misclassified examples with confidence scores
- Mean and p95 batch inference latency
- Python, scikit-learn, configuration, and random-seed metadata

Validation metrics guide model selection. Test metrics are read only for the
final comparison. No metric from `data/sample_feedback.csv` should appear on a
resume because it is a pipeline fixture, not a benchmark.

## Next experiment

Before Part 3, train both approaches on a public, redistribution-compatible
customer-feedback dataset. Record the dataset version, split fingerprints,
hardware, runtime, and model-selection rule. Promote the transformer only when
its quality gain justifies its latency and operational cost.
