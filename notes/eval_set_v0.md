# eval set v0

`eval_set_v0` is the first read-only validation layer for `DocSpectrum`.

Generated artifacts:

- `E:/output/DocSpectrum/eval_set_v0_18_n2`

Inputs:

- `E:/output/DocSpectrum/object_registry_v0/object_registry_v0.csv`
- `E:/output/DocSpectrum/object_registry_v0/address_tei_consistency_v0.csv`
- `E:/output/DocSpectrum/comparison_results_v0_3_18_n2/comparison_results_v0_3.csv`

## Purpose

This layer validates the mechanism; it does not tune scoring.

Two axes are kept separate:

- Axis A: content/system similarity, checked through `idf_similarity_v0_3` and domain-anchored section expectations.
- Axis B: size/TEI distance, checked through z-normalized TEI distance and future count/correlation analyses.

TEI/domain fields remain eval/profile context. They do not enter core scoring.

## Outputs

- `eval_pair_labels_v0.csv`: all pairwise rows with eval buckets, TEI distance, section expectation labels and ground-truth risk flags.
- `same_address_section_gradient_v0.csv`: same-address OV/GVS rows for Axis A sanity checks.
- `eval_section_summary_v0.csv`: section-level medians and expectation roles.
- `eval_set_v0.json`: summary metrics and rank checks.

## TEI Features

TEI distance uses z-score normalization over available object values:

- `tei_norm_building_volume_m3`
- `tei_norm_floors_count`
- `tei_norm_height_m`
- `tei_norm_apartments_count`
- `tei_norm_total_area_m2`
- `tei_norm_footprint_area_m2`

## Eval Buckets

- `same_address_cross_system`: same normalized address, different OV/GVS subgroup.
- `near_tei_same_section`: non-same-address pair with low TEI z-distance.
- `mid_tei_same_section`: middle TEI z-distance.
- `far_tei_same_section`: high TEI z-distance.

Same-address rows with TEI inconsistency are flagged as `tei_inconsistent_same_address` so they are not treated as clean ground truth.

## Current Run

Rows:

- eval pair labels: `1190`
- same-address cross-system rows: `24`
- same-address consistency: `24 consistent`

Eval buckets:

- `same_address_cross_system`: `24`
- `near_tei_same_section`: `290`
- `mid_tei_same_section`: `574`
- `far_tei_same_section`: `302`

TEI z-distance thresholds:

- near q25: `0.8579`
- far q75: `1.7590`
- threshold basis: non-same-address unique object pairs only

Axis checks:

- Axis A same-address primary rows: `18`
- Spearman expected section rank vs `idf_similarity_v0_3`: `0.9143`
- Spearman expected section rank vs section percentile: `0.8967`
- Axis B TEI distance vs `idf_similarity_v0_3`: `-0.0560`
- Axis B TEI distance vs `combined_similarity_v0_2`: `-0.0548`

Interpretation:

- Axis A sanity is strong: the metric follows the domain-anchored section/system gradient without using TEI in scoring.
- Axis B is intentionally not explained by jaccard similarity alone; size/TEI effects should be evaluated through counts and correlation layers, not by forcing content similarity to encode scale.
- No current same-address eval row is TEI-inconsistent; the inconsistency guard is for future expanded/post-expertise corpora.

## Limits

- This is a scaffold, not a fitted model.
- Rank checks are preferred over absolute thresholds.
- Current corpus is one organization and pre-expertise.
- Before/after expertise validation is not implemented yet.
- Graphical validation is deferred.
