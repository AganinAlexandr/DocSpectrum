# Org alias registry v0

This layer groups OCR/title variants of the same organization before any
organization-level handwriting experiment.

Inputs:
- all `title_authorship_range_*_results_v0/title_authorship_parties_v0.csv`;
- optional `E:/commons/DocSpectrum/?????????_???????.xlsx` for canon names;
- optional `inputs/org_alias_human_overrides_v0.csv` for confirmed names.

Rules:
- title pages remain the source of truth for role structure;
- `????????????` only normalizes the first title pair when it already exists;
- `?????????????` only normalizes the real executor, especially on pages 3+;
- human overrides only change canonical display naming and never rewrite raw evidence.

Outputs:
- `org_alias_registry_v0.csv`;
- `org_alias_variants_v0.csv`;
- `org_alias_review_shortlist_v0.csv`.
