# Expert quality experiment C v0

`tools/build_expert_quality_experiment_c_v0.py` productizes the first three
steps from HC-20260621-017 and T-20260621-020:

1. registry parsing and candidate/gold cells;
2. near-identity gate over original pre-expertise KR/POS sections;
3. cross-expert arena construction.

## Method boundary

The cell key is `(organization, work_type, section_code)`. A candidate needs
at least two objects and two distinct experts. A gold cell needs at least two
human-labeled anchor experts with first-round remarks.

The gate uses:

- size-invariant element composition from `page_summary.csv`;
- five-token shingle Jaccard from `text_segments.csv`.

The gate is pair-level. A group may have exported objects without every pair
being nearly identical. The arena includes cross-expert pairs with shingle
Jaccard at least `0.70`; `gate_status` distinguishes groups with and without
such pairs. It is an admission test for a shared defect substrate, not an
expert-quality verdict.

## Privacy and interpretation

Expert names are used only in memory. Generated artifacts contain SHA-1
identity hashes and generic roles: `ceiling_1_a`, `ceiling_1_b`, `floor_3`,
and `holdout`.

Class 1 is the ceiling of the quality scale. The holdout expert is evaluated
later through variance across review sessions, not only an average clean rate.

The following remain deliberately blocked:

- recall and remark typing until remark content is supplied by the owner;
- pre/post-expertise pair delta until corrected document versions exist;
- any punitive or person-level production conclusion.

## Outputs

Default output: `E:/output/DocSpectrum/expert_quality_experiment_c_v0`.

- `expert_quality_registry_rows_v0.csv`
- `expert_quality_groups_v0.csv`
- `expert_quality_gate_groups_v0.csv`
- `expert_quality_arena_pairs_v0.csv`
- `expert_quality_arena_cells_v0.csv`
- `expert_quality_experiment_c_v0.json`

Use `--assert-reference` for the current fixed-corpus acceptance run.
