# Part 2: Modeling and Evaluation

## Experiment design

Part 2 establishes a classical lower bound before spending GPU time on a
transformer. Each task receives an independent TF-IDF and class-balanced
logistic-regression pipeline. This makes coefficients inspectable, inference
fast, and failure analysis straightforward.

The optional transformer entry point fine-tunes a Hugging Face encoder one task
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
  --model-name microsoft/deberta-v3-small \
  --epochs 4 \
  --max-length 256 \
  --train-batch-size 16 \
  --learning-rate 2e-5 \
  --class-weighted
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

The command writes the selected model, tokenizer, model card, test predictions,
and a JSON report containing per-class scores, calibration, behavioral slices,
and error examples. For sentiment, omit `--class-weighted` unless validation
results show that weighting helps. A CUDA GPU is recommended for the DeBERTa
candidate; the command also works on CPU, but training is substantially slower.

## Promotion rule

Promote a transformer only when it beats the corresponding frozen-test
macro-F1 (0.5831 sentiment or 0.6439 aspect), improves minority-class recall,
and has an acceptable latency and memory cost. Never select hyperparameters on
the test set. Record dataset version, split fingerprints, hardware, runtime,
configuration, and failed candidates as well as the winner.
