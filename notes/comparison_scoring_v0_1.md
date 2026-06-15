# comparison scoring v0.1

`comparison_results_v0_1` is a scoring-hygiene checkpoint before adding the text-semantic axis.

Generated artifacts:

- `E:/output/DocSpectrum/comparison_results_v0_1_18_n2`

Input corpus:

- `E:/output/DocSpectrum/element_base_v0_18_n2`
- `1190` same-section pairs

## Policy

`feature_cosine_v0` is kept as a diagnostic metric and removed from scoring.

The scoring field is now:

- `signature_similarity_v0_1`

It uses exact structural signature axes:

- `page_signature_jaccard`, weight `0.40`
- `table_layout_jaccard`, weight `0.35`
- `table_content_jaccard`, weight `0.25`

Weights are rescaled over applicable scoring axes. Axis statuses are written explicitly:

- `measured`
- `measured_zero`
- `not_applicable`
- `missing`

## Expanded Corpus Run

`comparison_results_v0_1_18_n2` contains `1190` rows.

Signature similarity v0.1 by section:

| Section | Pairs | Min | Median | Max |
|---|---:|---:|---:|---:|
| АР | 153 | 0.1500 | 0.3533 | 0.7333 |
| КР | 153 | 0.1667 | 0.3706 | 0.7538 |
| ИД | 153 | 0.7025 | 0.8545 | 0.9265 |
| ИОС5.1 | 153 | 0.0905 | 0.1691 | 0.5038 |
| ИОС5.4.1 | 153 | 0.0421 | 0.2043 | 0.6147 |
| ИОС5.5.1 | 153 | 0.0261 | 0.1821 | 0.4522 |
| ПОКР | 136 | 0.1083 | 0.2946 | 0.6444 |
| СМ | 136 | 0.0358 | 0.0862 | 0.5353 |

Axis status counts:

- `measured`: `3309`
- `measured_zero`: `261`

## Interpretation

The raw-cosine floor is no longer part of the score. This makes low structural overlap visible: for example, `СМ` median changes from `0.5851` in v0 fast scoring to `0.0862` in v0.1 signature scoring.

This is not the final similarity model. It intentionally does not include:

- near-match signatures;
- text-semantic axis;
- expert eval weights.

The next scoring layer should add text-semantic evidence as a first-order axis, not as a domain/QC feature.
