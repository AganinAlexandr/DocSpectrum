# Validation phase v1

## Generator-ready gate

- Goal: build a reproducible validation and retrieval benchmark before opening the reserved 13-object rewrite holdout.
- Specification source: shared `HC-20260621-018` and `HC-20260621-019`.
- Work type: validation first; product assembly only for the result envelope; no exploratory fitting on the holdout.
- Inputs: committed metric code and existing RSPK/NK artifacts under `E:\output\DocSpectrum`.
- Outputs: golden regression, controlled text/table injection, retrieval metrics, shortlist audit, threshold calibration, result envelope, then graphics.
- Acceptance: every milestone has `--assert-reference`, unit tests, coverage, and interpretation limits.
- Not touched: `E:\Archi` before/after scores, train libraries, legal borrowing labels, and unknown author identities.

## Milestone order

1. Freeze validated behavior as executable golden anchors.
2. Build a controlled source-level injection benchmark for text and tables before feature extraction.
3. Measure retrieval recall/precision/rank stability and shortlist completeness.
4. Calibrate candidate-routing thresholds without creating legal verdicts.
5. Emit a multi-axis result envelope with provenance, coverage, confidence, and limitations.
6. Add a graphics axis and a separate source-level graphics injection benchmark.
7. Run the natural 13-object holdout once only after the contracts are frozen.

## Golden scope

The golden suite protects established denominators and conclusions. It does not claim new accuracy. Intentional model or corpus changes must explain and version any golden update rather than silently overwriting expected values.
