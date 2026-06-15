# expanded corpus 35 replication v0

`RP-013` reruns the current DocSpectrum measurement chain on the expanded
RSPK UUiR corpus and treats the result as replication, not as weight fitting.

Generated artifacts:

- `E:/output/DocSpectrum/element_base_v0_35_n2`
- `E:/output/DocSpectrum/corpus_frequency_v0_35_n2`
- `E:/output/DocSpectrum/comparison_results_v0_2_35_n2`
- `E:/output/DocSpectrum/comparison_results_v0_3_35_n2`
- `E:/output/DocSpectrum/eval_set_v0_35_n2`
- `E:/output/DocSpectrum/axis_b_correlations_v0_35_n2`

## Scope

- Axis A: content/system gradient sanity check on same-address cross-system pairs.
- Axis B: count/TEI correlations with disjoint replication: `first18`, `added17`, `all`.
- Axis C: out of scope until a cross-organization corpus is available.
- Scoring weights are not tuned from this run.

## Coverage

- documents: `279`
- objects: `35`
- UNKNOWN sections: `0`
- same-section pairs: `4450`

Documents by section:

| Section | Documents | Pairs |
|---|---:|---:|
| AR | 35 | 595 |
| KR | 35 | 595 |
| ID | 35 | 595 |
| IOS5.1 | 35 | 595 |
| IOS5.4.1 | 35 | 595 |
| IOS5.5.1 | 35 | 595 |
| SM | 34 | 561 |
| POKR | 23 | 253 |
| POS | 12 | 66 |

The expanded corpus is intentionally used in "library = all available sections"
mode. It is not a strict 35 x 8 matrix.

## v0.3 medians

Median `idf_similarity_v0_3` by section:

| Section | Median |
|---|---:|
| AR | 0.6072 |
| KR | 0.6628 |
| ID | 0.9211 |
| IOS5.1 | 0.5888 |
| IOS5.4.1 | 0.3227 |
| IOS5.5.1 | 0.5682 |
| POKR | 0.6077 |
| POS | 0.5674 |
| SM | 0.2340 |

## Axis A

Same-address cross-system rows:

- total: `40`
- TEI-consistent: `32`
- TEI-inconsistent guard: `8`
- primary rows after excluding diagnostics and inconsistent same-address pairs: `24`

Primary gradient:

- Spearman expected rank vs `idf_similarity_v0_3`: `0.9137`
- Spearman expected rank vs section percentile: `0.8653`

The `1680/1684` inconsistent same-address case now exercises the guard and is
excluded from clean primary ground truth.

## Axis B replication

The Axis B builder now emits:

- `axis_b_correlations_v0.csv` with `subset_label`, approximate p-value and BH q-value.
- `axis_b_replication_v0.csv` with `replication_status` for strong first18 signals.

Correlation rows:

- `all`: `3096`
- `first18`: `2400`
- `added17`: `2629`

Replication statuses for first18 candidates with `abs_spearman >= 0.45`:

| Status | Count |
|---|---:|
| persisted | 69 |
| regressed_to_zero | 187 |
| sign_flip | 9 |
| insufficient_added17 | 14 |

This is the intended anti-overfitting result: many strong first18 correlations
do not survive the disjoint added17 check.

FDR summary:

- `all`: 32 correlations flagged at `q <= 0.10`.
- `first18`: 0 correlations flagged at `q <= 0.10`.
- `added17`: 0 correlations flagged at `q <= 0.10`.

The FDR layer is approximate and should be interpreted as a sanity filter, not
as final statistics.

## Performance

`compare_pairs_v0_3.py` now pre-indexes IDF as
`(section_code, entity_kind) -> {entity_hash: idf}`.

This removes the previous per-pair full scan over `entity_frequency_v0.csv` and
keeps the 35-object v0.3 run practical for `4450` pairs.
