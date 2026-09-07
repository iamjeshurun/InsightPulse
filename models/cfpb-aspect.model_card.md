# Model Card: InsightPulse TF-IDF Baseline

## Overview

This artifact is an interpretable classical baseline using word and bigram
TF-IDF features with one class-balanced logistic-regression classifier per
task. Its purpose is to establish a reproducible lower bound for transformer
experiments—not to serve as a universal sentiment model.

## Evaluation

| Task | Test examples | Macro-F1 | Expected calibration error |
| --- | ---: | ---: | ---: |
| aspect | 843 | 0.6419006529601639 | 0.22575586009794793 |

Mean inference latency: 0.0830 ms/example.

## Appropriate use

Use for experimentation on English-language customer feedback resembling the
training domain. Predictions should support human decisions, not make automated
employment, credit, medical, legal, or other high-impact decisions.

## Limitations

- Small or unrepresentative test sets cannot support reliable performance claims.
- Lexical models struggle with sarcasm, implicit sentiment, and domain shift.
- Probability calibration and subgroup performance require ongoing monitoring.
- PII redaction and dataset licensing remain upstream responsibilities.

## Reproducibility

Random seed: `42`  
Python: `3.13.13`  
scikit-learn: `1.9.0`
