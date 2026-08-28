# Annotation Guidelines

## General rules

Annotate the meaning expressed by the customer, not the annotator's opinion.
Use the full conversational context when it is available. Mark genuinely
ambiguous examples for adjudication instead of guessing. Two annotators should
label an evaluation subset independently; report agreement before model claims.

## Sentiment

- **Positive:** clear approval, satisfaction, or favorable experience.
- **Neutral:** factual, mixed without a dominant polarity, or no clear opinion.
- **Negative:** dissatisfaction, criticism, or an unfavorable experience.

## Intent

- **Praise:** expresses satisfaction without requesting remediation.
- **Complaint:** reports a problem or asks for a problem to be fixed.
- **Feature request:** proposes a new capability or improvement.
- **Churn risk:** explicitly threatens or strongly signals cancellation.
- **Other:** does not reliably fit the preceding categories.

## Urgency

- **High:** security, payment, complete outage, safety, legal risk, or explicit
  immediate business impact.
- **Medium:** degraded core functionality that needs timely attention.
- **Low:** praise, questions, minor inconvenience, and non-blocking requests.

## Edge cases

- For mixed sentiment, label the dominant overall sentiment and preserve
  aspect-level differences for the aspect annotation stage.
- Sarcasm should be labeled by intended meaning and flagged for error analysis.
- A feature request is not automatically negative.
- Cancellation language should be `churn_risk`, even when it also complains.
