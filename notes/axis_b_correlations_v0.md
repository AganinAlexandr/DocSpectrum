# axis B correlations v0

`axis_b_correlations_v0` is the first read-only export for size/TEI validation.

Generated artifacts:

- `E:/output/DocSpectrum/axis_b_correlations_v0_18_n2`

Inputs:

- `E:/output/DocSpectrum/object_registry_v0/object_registry_v0.csv`
- `E:/output/DocSpectrum/element_base_v0_18_n2/documents_index.csv`
- `E:/output/DocSpectrum/corpus_frequency_v0_18_n2/section_typicality_v0.csv`

## Purpose

Axis B is about size and quantity. It should not be forced into content Jaccard.

This layer joins object TEI features to absolute document/entity counts and exports rank correlations.

TEI/domain fields remain eval/profile context and do not enter core scoring.

## Outputs

- `axis_b_document_metrics_v0.csv`: document-level TEI + PDF counts + entity occurrence counts.
- `axis_b_correlations_v0.csv`: Spearman correlations by `section_code`, TEI feature and metric.
- `axis_b_tei_bucket_summary_v0.csv`: low/mid/high TEI bucket medians for selected counts.
- `axis_b_correlations_v0.json`: summary and top absolute correlations.

## TEI Features

- `tei_norm_building_volume_m3`
- `tei_norm_floors_count`
- `tei_norm_height_m`
- `tei_norm_apartments_count`
- `tei_norm_total_area_m2`
- `tei_norm_footprint_area_m2`

## Modeling Notes

- Spearman rank correlation is preferred because equipment choices are stepped.
- Absolute counts and per-page ratios are both exported to control document-size effects.
- Current corpus is one organization and pre-expertise, so correlations are exploratory.
- Strong correlations are candidate signals, not proof of causal relation.

## Current Run

Rows:

- document metric rows: `143`
- correlation rows: `2395`
- TEI bucket summary rows: `108`

Correlation families:

- entity metrics: `1175`
- document counts: `625`
- document ratios: `595`

Top exploratory signals by absolute Spearman:

| Section | TEI feature | Metric | Family | n | Spearman |
|---|---|---|---|---:|---:|
| ИД | `tei_norm_total_area_m2` | `total_text_words` | document_count | 17 | 0.7947 |
| ИОС5.5.1 | `tei_norm_height_m` | `entity_text_segment_typical_occurrences` | entity | 18 | 0.7844 |
| ИОС5.4.1 | `tei_norm_floors_count` | `table_cells_per_page` | document_ratio | 18 | 0.7831 |
| ИОС5.4.1 | `tei_norm_total_area_m2` | `table_cell_count` | document_count | 17 | 0.7796 |
| ИД | `tei_norm_footprint_area_m2` | `element_count` | document_count | 18 | 0.7734 |
| КР | `tei_norm_total_area_m2` | `entity_page_signature_shared_rare_occurrences` | entity | 17 | 0.7699 |

First interpretation:

- Axis B now has measurable candidate signals; it is no longer only "absent from jaccard".
- Several strong correlations are count/ratio based, as expected for the size axis.
- Signals in engineering sections (`ИОС5.4.1`, `ИОС5.5.1`) are especially relevant to HC-006 equipment/pressure hypotheses.
- These are exploratory correlations on a small, pre-expertise, one-organization corpus and should be treated as candidates for review, not calibrated rules.

Encoding note:

- This layer assumes upstream CSV artifacts are already decoded and normalized.
- Source PDFs/XMLs may contain several real-world encodings; encoding detection/repair belongs in the extractor/registry layer, not in the Axis B correlation builder.
