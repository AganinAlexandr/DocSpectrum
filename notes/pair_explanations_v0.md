# pair explanations v0

This layer explains why selected pairs are similar by localizing shared entity
hashes back to pages, text segments, table cells, table signatures and page
signatures.

It is an explanation layer over existing `comparison_result_v0_3` artifacts. It
does not change scoring.

## Privacy Rule

The explanation artifacts remain hash-only:

- no raw text is written;
- text-derived entities are represented by hashes;
- locations point to page numbers, segment ids, table ids and cell coordinates.

This keeps the current DocSpectrum privacy invariant intact while making the
pairwise result inspectable.

## Tool

`tools/explain_pair_shared_entities_v0.py`

Default input set:

- top cross-organization pairs from
  `E:/output/DocSpectrum/cross_org_research_v0/cross_org_top_pairs_v0.csv`;
- combined export view:
  `E:/output/DocSpectrum/export_rpsk35_nk34_object_view`;
- combined element base:
  `E:/output/DocSpectrum/element_base_v0_rpsk35_nk34`;
- combined corpus frequency:
  `E:/output/DocSpectrum/corpus_frequency_v0_rpsk35_nk34`;
- combined v0.3 comparison results:
  `E:/output/DocSpectrum/comparison_results_v0_3_rpsk35_nk34`.

Generated first run:

- `E:/output/DocSpectrum/pair_explanations_cross_top3_v0/pair_explanations_v0.json`
- `E:/output/DocSpectrum/pair_explanations_cross_top3_v0/pair_explanation_summary_v0.csv`
- `E:/output/DocSpectrum/pair_explanations_cross_top3_v0/pair_shared_entities_v0.csv`

Run parameters:

- top cross pairs per section: `3`
- pair count: `24`
- shared entity rows: `724`
- per-kind entity limit: `10`
- location limit: `8`

## First Findings

Most top cross-organization pairs are text-only bridges:

- `АР`: no shared page/table-layout/table-content signatures in top pairs;
- `ИОС5.1`: no shared page/table-layout/table-content signatures in top pairs;
- `ИОС5.5.1`: no shared page/table-layout/table-content signatures in top pairs;
- `КР`: no shared page/table-layout/table-content signatures in top pairs;
- `ПОКР`: no shared page/table-layout/table-content signatures in top pairs;
- `ПОС`: no shared page/table-layout/table-content signatures in top pairs;
- `СМ`: high text overlap tail, but no shared structural signatures.

`ИОС5.4.1` is the meaningful exception:

- top cross pairs have many shared text/table-cell hashes;
- top cross pairs have `3` shared `table_layout_signature` hashes;
- top cross pairs have `0` shared `table_content_signature` hashes;
- top cross pairs have `1` shared `page_signature`, but it is a typical
  image-only page signature and should stay diagnostic.

The repeated `ИОС5.4.1` table-layout matches are localized to repeated tables:

- left side: pages around `18-26`;
- right side: pages around `21-32`;
- layout form: `8x4`, `22 cells`;
- frequency bucket: `shared_rare`.

Interpretation:

- This is not evidence of whole-section copying: the overall cross score remains
  low (`max idf_similarity_v0_3 = 0.1196` for this section).
- It is also not just boilerplate text: the shared table-layout signatures show
  a repeated technical table form.
- Since table content signatures do not match, the current evidence points to a
  common type of engineering table/form rather than identical table content.
- This is the first useful "typical group of elements" candidate in the
  cross-organization corpus: repeated text/table-cell fragments plus recurring
  `8x4 / 22-cell` table layouts in `ИОС5.4.1`.

## Consequence

The cross-org research should now separate three cases:

- text-only bridge: common wording/normative phrases;
- layout bridge: same table/page form but changed content;
- content bridge: same or near-same table/page content.

The current RSPK-vs-NK top cross pairs mostly fall into the first case, while
`ИОС5.4.1` contains a small but real layout bridge.

## Next Step

Add a compact pair-classification layer on top of explanations:

- `text_only_bridge`;
- `table_layout_bridge`;
- `table_content_bridge`;
- `page_signature_bridge`;
- `low_signal`.

This classification should be diagnostic first, not a scoring replacement.
