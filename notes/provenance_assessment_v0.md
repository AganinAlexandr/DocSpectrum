# Provenance assessment v0

## Purpose

RP-024 and HC-012 established that the strongest cross-organization overlaps
can be confirmed non-copy when both projects use the same third-party source.
This layer makes provenance an explicit gate before borrowing interpretation.

It is additive: page near-match scores and historical v0 library classes are
not rewritten.

## Rules

- `third_party` material is ineligible for borrowing interpretation;
- `unassessed` provenance is blocked, not assumed organization-authored;
- only expert-supported `organization_authored + distinctive` content is
  eligible for deeper borrowing review;
- eligibility is not a verdict;
- organization/GIP/executor handwriting is evaluated only on the
  organization-authored residual.

## Current corpus

The 240 cross-organization body-page candidates become:

```text
expert-assessed third-party / confirmed non-copy: 30
unassessed / borrowing blocked:                   210
organization-authored borrowing candidates:        0
```

The 30 assessed cases retain their source classes:

- `external_form`;
- `software_generated`;
- `vendor_technical_material`.

## Next review sample

The remaining 210 are not reviewed by descending score. The tool creates a
small stratified sample by:

- section;
- low/middle/high text-overlap band within the section;
- structure-dominant vs text-stronger ratio band.

Two cases are selected per populated stratum. This searches for provenance
novelty and medium-band organization-authored material instead of repeatedly
showing the highest-scoring manufacturer and estimate templates.

The current corpus produces `16` cases: `8` from `ИОС5.4.1` and `8` from `СМ`.
Only populated strata are represented; empty combinations are not synthesized.

## Outputs

Generated under `E:/output/DocSpectrum/provenance_assessment_v0`:

- `page_provenance_assessment_v0.csv`;
- `page_provenance_review_sample_v0.csv`;
- `provenance_assessment_v0.json`.

Power Query views:

- `analytics/pq/ProvenanceAssessment_v0.pq`;
- `analytics/pq/ProvenanceReviewSample_v0.pq`.

Human review interfaces for the current sample:

- `E:/commons/DocSpectrum/page_provenance_sample16_review_v0.html`;
- `E:/commons/DocSpectrum/page_provenance_sample16_compact_v0.csv`.

## Limits

- Only 30 cases have expert provenance labels.
- The layer has no positive borrowing control.
- No borrowing threshold may be calibrated until positive-control data exists.
- Source-class inference is not automated in v0; unreviewed cases remain
  explicitly unassessed.
