# PharmaWatch AI — Evaluation Report

Generated: 2026-10-27T12:36:03Z
Model: claude-sonnet-5-5
Dataset: golden_dataset.json (30 cases)

## Summary

- Total cases: 30
- Passed: 29
- Failed: 1
- Pass rate: 96.7%

## Metrics

| Metric | Score | Threshold | Status |
|---|---|---|---|
| Retrieval Accuracy | 100.0% | >= 85% | PASS |
| Answer Faithfulness | 84.1% | >= 90% | FAIL |
| Hallucination Rate | 0.0% | <= 10% | PASS |
| Classification Accuracy | 90.0% | >= 80% | PASS |
| Reportability Accuracy | 90.0% | >= 85% | PASS |
| Escalation Appropriateness | 100.0% | >= 75% | PASS |
| Latency p50 | 7686 ms | < 5000 ms | FAIL |
| Latency p95 | 13967 ms | < 15000 ms | PASS |
| Source Citation Rate | 100.0% | >= 95% | PASS |

## Failed Cases

- **case_018**: expected severity='serious', got 'non-serious'; expected reportable=True, got None

## Notes

- `hallucination_rate` and `answer_faithfulness` are computed with an embedding-based claim-support heuristic (sentence-transformers cosine similarity against retrieved chunks, calibrated threshold - see `CLAIM_SUPPORT_SIMILARITY_THRESHOLD` in `src/evaluation/metrics.py`), not a second LLM judge.
- `escalation_appropriateness` is measured only over the dataset's `ambiguous` classification subcategory (cases with missing critical information, which must be escalated rather than guessed).
- Any metric below its threshold is reported as-is below, not hidden or adjusted - see the project README for the honesty-over-polish rationale.
