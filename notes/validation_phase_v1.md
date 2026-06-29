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

1. Freeze current artifact behavior and reviewed relational conclusions as executable golden anchors.
2. Build a controlled source-level injection benchmark for text and tables before feature extraction.
3. Measure retrieval recall/precision/rank stability and shortlist completeness.
4. Calibrate candidate-routing thresholds without creating legal verdicts.
5. Emit a multi-axis result envelope with provenance, coverage, confidence, and limitations.
6. Add a graphics axis and a separate source-level graphics injection benchmark.
7. Run the natural 13-object holdout once only after the contracts are frozen.

## Golden scope

The active `golden_anchors_v1` suite protects current frozen-artifact behavior and explicitly reviewed relational conclusions. It does not claim that every current artifact value was newly validated, and it does not claim new model accuracy. Each anchor records its originating RP and whether it is an exact reviewed value, an artifact decomposition of a reviewed aggregate, or a conservative conclusion floor.

`golden_anchors_v0` is retained as the reviewed pilot snapshot. It is superseded by v1 because v0 used permissive numeric coercion, hand-bracketed GIP values, and incomplete per-anchor provenance. Intentional model or corpus changes must explain and version any golden update rather than silently overwriting expected values.

The `474` combined-report denominator and `475` entity-corpus denominator remain separate exact snapshots. Their one-document difference is documented but is not promoted to a universal invariant: the two artifacts have different downstream inclusion scopes.

## Milestone 2 status

The isolated source-lineage fixture group is prepared under `source_lineage_fixtures_v0`: 16 canonical sources and 104 text/table query variants. This is component-level lineage ground truth, not full-document mixing. Explorer extraction, exhaustive retrieval, shortlist audit, and sensitivity metrics remain pending.
