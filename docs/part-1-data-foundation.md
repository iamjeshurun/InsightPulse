# Part 1: Data Foundation

## Design decisions

The first milestone deliberately uses only the Python standard library. This
keeps ingestion reproducible and separates data-quality failures from package
installation problems. CSV and JSONL cover local files and exported records;
connectors can be added later behind the same record contract.

Validation is strict for structural fields and permissive for labels, which may
be absent in inference data. Invalid records are preserved in quarantine with
their row number and reasons. Duplicate detection uses both stable IDs and a
SHA-256 fingerprint of normalized, redacted text.

Splits are deterministic and created only after validation, redaction, and
deduplication. This prevents exact duplicates leaking across evaluation sets.
Part 2 will add group-aware and stratified splitting where dataset size and
customer/product grouping justify it.

## Quality gates

- Every accepted record conforms to the documented schema.
- Raw PII patterns covered by the redactor never enter processed splits.
- Exact normalized-text duplicates cannot cross splits.
- Identical inputs and configuration yield identical split files.
- Every artifact is checksummed in a versioned manifest.

## Known limitations

- Regex redaction is not named-entity recognition and cannot guarantee removal
  of names, addresses, or unusual identifier formats.
- Exact duplicate detection does not detect paraphrases or near duplicates.
- Small datasets may produce empty validation or test partitions.
- Random splits can overestimate generalization when one customer contributes
  multiple related records; group-aware splitting is planned for Part 2.
