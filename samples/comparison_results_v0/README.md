# comparison_results_v0

First exploratory same-section comparisons for `element_base_v0`.

Generated at:

- `2026-06-14T14:24:16+00:00`

The score is intentionally simple:

- `feature_cosine_v0` - cosine over a compact numeric vector
- `page_signature_jaccard` - multiset overlap of page layout signatures
- `table_layout_jaccard` - multiset overlap of table layout signatures
- `table_content_jaccard` - multiset overlap of hashed table content

`weighted_similarity_v0` is a temporary weighted mix for research only.
