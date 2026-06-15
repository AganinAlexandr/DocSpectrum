# axis B page-count control v0

`RP-014` adds a read-only page-count control layer to Axis B.

Generated artifacts:

- `E:/output/DocSpectrum/axis_b_correlations_v0_35_n2/axis_b_correlations_v0.csv`
- `E:/output/DocSpectrum/axis_b_correlations_v0_35_n2/axis_b_replication_v0.csv`
- `E:/output/DocSpectrum/axis_b_correlations_v0_35_n2/axis_b_shortlist_page_control_v0.csv`

## Purpose

RP-013 produced a strict Axis B shortlist:

- `persisted` on disjoint replication
- `all35` FDR significant at `q <= 0.10`
- 28 candidate rows

RP-014 checks whether those candidates survive a simple document-size control:

- partial Spearman of `TEI feature` and `metric`
- control variable: `page_count`
- implementation: Pearson correlation of rank residuals after regressing ranks on `page_count` ranks
- default survival threshold: `abs(partial_spearman_page_count) >= 0.45`

This remains an eval/profile layer and does not change scoring.

## Current Result

The strict 28-row shortlist survives page-count control:

| Page-control class | Count |
|---|---:|
| survives_page_control | 28 |
| page_size_confounded | 0 |
| not_controlled | 0 |

Family split:

| Family | Count |
|---|---:|
| entity | 15 |
| document_ratio | 6 |
| document_count | 7 |

Interpretation:

- The high-confidence Axis B candidates are not explained away by page count alone.
- The 7 `document_count` rows still require cautious reading: they survive page-count control, but may still reflect other size proxies.
- Entity and ratio rows remain the cleaner first-order Axis B candidates.

## Strongest Survivors

Top surviving rows by absolute partial Spearman:

| Section | TEI feature | Metric | Family | Spearman | Partial |
|---|---|---|---|---:|---:|
| IOS5.5.1 | `tei_norm_floors_count` | `entity_text_segment_typical_occurrences` | entity | 0.7911 | 0.8474 |
| IOS5.5.1 | `tei_norm_height_m` | `entity_text_segment_typical_occurrences` | entity | 0.7301 | 0.7848 |
| IOS5.5.1 | `tei_norm_floors_count` | `text_segment_count` | document_count | 0.6525 | 0.7447 |
| IOS5.5.1 | `tei_norm_floors_count` | `entity_text_segment_shared_rare_occurrences` | entity | -0.7211 | -0.7432 |
| IOS5.5.1 | `tei_norm_building_volume_m3` | `entity_text_segment_typical_occurrences` | entity | 0.6474 | 0.7055 |

## Limitations

- This is page-count control, not a full engineering causal model.
- It does not control for all size proxies such as total area, building volume, or element count.
- `tei_norm_apartments_count` remains weak in this corpus because only a few objects have that TEI field populated.
- Cross-organization validation is still required before treating Axis B patterns as stable organizational/product signals.
