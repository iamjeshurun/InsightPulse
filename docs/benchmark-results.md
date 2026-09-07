# Reproducible baseline benchmark

Run date: 2026-09-06. Hardware-specific latency was measured locally on the
same machine as training. Seed 42 and scikit-learn 1.9.0 were used.

| Task | Classes | Train / validation / test | Accuracy | Macro-F1 | Mean latency per example |
| --- | ---: | ---: | ---: | ---: | ---: |
| DynaSent sentiment | 3 | 13,065 / 720 / 720 | 0.5847 | 0.5831 | 0.0162 ms |
| Bitext intent | 27 | 21,520 / 2,768 / 2,584 | 0.9915 | 0.9910 | 0.0223 ms |
| CFPB aspect | 8 | 6,488 / 792 / 843 | 0.7236 | 0.6439 | 0.2222 ms |

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
sets come from the same generation process. The result demonstrates that the
pipeline can learn and serve a 27-class problem; it does not establish
real-world generalization. A later evaluation on manually labeled organic
support requests is required before production use.

The aspect baseline uses January 2019 CFPB complaints. Of 19,688 exported
records, 8,123 narratives remained after removing empty, short, and exact
duplicate text. The compact aspect label is deterministically derived from the
consumer-selected CFPB product, issue, and sub-issue—not inferred by a model.
The original nine-class taxonomy placed only two test examples in
`customer_service`, making its score unstable. The refined eight-class taxonomy
merges that insufficiently supported class into `other`; macro-F1 consequently
rises from 0.5702 to 0.6439 without changing the split. Class-aware transformer
training must beat that stronger target before it is promoted.

## Transformer experiment

The transformer runner now supports dynamic padding, maximum sequence length,
configurable learning rate and batch size, square-root inverse-frequency class
weights, validation-based checkpoint selection, and the same detailed held-out
evaluation contract as the baseline.

An initial CPU-feasible capacity check fine-tuned
`google/bert_uncased_L-2_H-128_A-2` for ten epochs with a 1e-4 learning rate,
batch size 32, maximum length 128, and class weighting. It reached 0.6785 test
accuracy and 0.5605 macro-F1, so it is explicitly rejected: it is 0.0834 below
the refined classical baseline. This negative result is useful evidence that a
two-layer encoder lacks sufficient capacity for the aspect task. The next
candidate is `microsoft/deberta-v3-small` on a GPU, evaluated on exactly the
same frozen splits.

## Reproduce

Follow `docs/datasets.md`, then run the two `insightpulse-baseline` commands.
Generated reports include per-class precision/recall/F1, confusion matrices,
expected calibration error, behavior slices, error examples, model files, and
run configurations. The generated artifacts are ignored by Git because model
files and third-party examples should be rebuilt from their documented sources.
