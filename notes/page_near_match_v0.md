# Page near-match v0

## Purpose

Exact page signatures are useful as a high-precision baseline, but they do not
represent near-identical pages whose counts, geometry or content changed
slightly. This research layer adds a generic page-level near-match search above
the existing element base.

The scorer is domain-neutral. Project-document title labels and organization
cohorts are external evaluation metadata and do not enter the similarity score.

## Inputs

- element base: `E:/output/DocSpectrum/element_base_v0_rpsk35_nk34`;
- explorer exports: `E:/output/DocSpectrum/export_rpsk35_nk34_object_view`;
- corpus frequency: `E:/output/DocSpectrum/corpus_frequency_v0_rpsk35_nk34`;
- title references: shared RSPK registry plus the DocSpectrum-owned NK input;
- cohorts: `RSPK=35`, `NK=34`.

Corpus:

```text
pages:       10826
title pages:   945
```

## Method

Candidate search uses normalized vectors built from:

- element counts by group;
- element-count composition;
- group-area totals;
- group-area composition;
- total element count.

Page size is deliberately excluded. The final score reranks the shortlist using
the same five structural components:

```text
0.30 count ratio
0.20 count composition
0.25 area ratio
0.15 area composition
0.10 total element-count ratio
```

Pages from the same document are excluded. Exact-signature candidates are
injected into the shortlist before reranking, so near-match cannot regress the
exact baseline.

Text and table hashes are diagnostic evidence after structural matching:

- text-segment Jaccard;
- shared and rare shared text-segment counts;
- shared-text global IDF;
- table-layout overlap;
- table-content overlap.

Rare text currently means `global_df_ratio <= 0.25`.

## Results

The generated neighbor table contains `108260` rows (`top 5` for both `any` and
`cross_org` modes).

Exact baseline:

```text
pages with an exact match in another document: 5481
exact matches recovered at top rank:           5481
exact recall:                                  1.0
```

Title-page cross-organization search:

```text
title pages:                         945
cross-org moderate near-match:       367
cross-org weak match:                578
cross-org similarity p10 / median / p90:
0.6417 / 0.6765 / 0.8110
```

This is the intended unlock: exact signatures found no cross-organization title
matches in RP-021, while near-match exposes a substantial structural bridge
without using page size or cohort labels in the score.

## Review Shortlist

The review shortlist keeps unique cross-organization, non-exact, top-1 page
pairs with:

- structural similarity at least `0.85`;
- at least one globally rare shared text segment;
- text-segment Jaccard at least `0.20`.

Result:

```text
review candidates:                  240
rare-text high overlap:              30
rare-text partial overlap:          210
ИОС5.4.1 <-> ИОС5.4.1:              160
СМ <-> СМ:                           80
```

The concentration is useful for investigation but is not proof of copying.
`ИОС5.4.1` is a plausible engineering-content bridge; `СМ` may also contain
standardized estimate wording or forms. Both require evidence inspection.

## Outputs

Generated under `E:/output/DocSpectrum/page_near_match_v0`:

- `page_near_match_neighbors_v0.csv`;
- `page_near_match_review_candidates_v0.csv`;
- `title_page_near_match_summary_v0.csv`;
- `page_near_match_v0.json`.

## Interpretation Limits

- This is a candidate generator, not a borrowing verdict.
- Thresholds are experiment defaults and are not yet a product contract.
- The corpus contains only two organizations.
- Text/table hash evidence cannot replace graphical or semantic comparison.
- Vector/image content is represented only through current element counts and
  group areas; dedicated graphical near-match remains future work.
- Organization, GIP and executor attribution require their corresponding
  external labels and separate evaluation.

## Next Step

Review the shortlist and calibrate whether rare-text evidence separates:

- normative cross-organization forms;
- shared technical content;
- genuine copy/foreign-template candidates.

After that calibration, near-match can feed the typical-element library and the
UC3 review layer without promoting every structural resemblance to a copying
claim.
