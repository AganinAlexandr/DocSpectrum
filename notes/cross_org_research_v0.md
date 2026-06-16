# cross-org research v0

This note captures the first research-only comparison between the RSPK UUiR
baseline and the NK-Engineering UUiR export set.

It is not a review packet yet. The goal is to inspect the new cross-organization
signal before deciding what should become an Opus-reviewed milestone.

## Inputs

- RSPK cohort: `E:/output/DocSpectrum/export`
- NK cohort: `E:/output/DocSpectrum/export_nk_34_object_view`
- combined export view: `E:/output/DocSpectrum/export_rpsk35_nk34_object_view`
- pairwise results: `E:/output/DocSpectrum/comparison_results_v0_3_rpsk35_nk34/comparison_results_v0_3.csv`
- research summary: `E:/output/DocSpectrum/cross_org_research_v0/`

The cohort labels are applied only after pairwise scoring. They are research
metadata and do not influence the core similarity calculation.

## Corpus Snapshot

- cohorts: `RSPK=35 objects`, `NK=34 objects`
- combined documents/bundles: `475`
- pairwise rows: `13534`
- pair type counts:
  - `within_rspk`: `4450`
  - `within_nk`: `2748`
  - `cross_nk_rspk`: `6336`
- unknown pair count: `0`

NK coverage is good for the main recurring sections but not uniform:

- `АР`: `32`
- `КР`: `32`
- `ИОС5.1`: `33`
- `ИОС5.4.1`: `32`
- `ПОКР`: `27`
- `СМ`: `27`
- `ИОС5.5.1`: `6`
- `ПОС`: `6`
- `UNKNOWN`: `1`

The single `UNKNOWN` file is kept diagnostic for now because combined UUiR
projects can package sections differently. We should not force it into a section
code until the domain rule is explicit.

## Within/Cross Similarity

Median `idf_similarity_v0_3` by section:

| section | within RSPK | within NK | cross RSPK/NK | separation gap |
| --- | ---: | ---: | ---: | ---: |
| ПОКР | 0.6437 | 0.7231 | 0.0114 | 0.6720 |
| АР | 0.6441 | 0.6118 | 0.0549 | 0.5731 |
| ИОС5.5.1 | 0.5732 | 0.6125 | 0.0469 | 0.5460 |
| КР | 0.6930 | 0.4345 | 0.0650 | 0.4987 |
| ИОС5.1 | 0.6004 | 0.5633 | 0.1023 | 0.4795 |
| ПОС | 0.5788 | 0.2997 | 0.0294 | 0.4099 |
| СМ | 0.2381 | 0.5460 | 0.0587 | 0.3334 |
| ИОС5.4.1 | 0.3567 | 0.2610 | 0.0381 | 0.2707 |

Interpretation:

- Cross-organization pairs are much lower than within-organization pairs across
  all comparable sections.
- The result is a strong first research signal for Axis C
  (organization/project handwriting).
- `ИОС5.5.1` and `ПОС` in NK have only `6` documents each (`15` within pairs),
  so their medians are small-n diagnostics.
- `СМ` remains special: RSPK has low within similarity while NK is much more
  homogeneous, so estimates for this section should stay cautious.

## NK vs RSPK Baseline

When computed in their separate libraries, NK is more heterogeneous than RSPK in
some sections and more homogeneous in others:

- stronger NK heterogeneity: `КР`, `ПОС`, `ИОС5.4.1`
- stronger NK homogeneity: `СМ`, `ПОКР`

In the combined library, the key observation is not the exact within-cohort
median, but the order-of-magnitude drop in cross-cohort similarity.

## Caveats

- This is a research checkpoint, not a reviewed milestone.
- Cohort separation is measured on one contrast pair: RSPK vs NK.
- The NK set has uneven section coverage.
- The current page-signature axis is still strictness-prone; the headline uses
  `idf_similarity_v0_3`, not page signature alone.
- Combined v0.3 generation is already heavy at `13534` pairs. Before scaling to
  more organizations, `compare_pairs_v0_3.py` needs a summary-only or
  skip-heavy-json mode.

## Nearest-Neighbor Check

Generated artifacts:

- `E:/output/DocSpectrum/cross_org_research_v0/cross_org_nearest_neighbors_v0.csv`
- `E:/output/DocSpectrum/cross_org_research_v0/cross_org_top_pairs_v0.csv`
- `E:/output/DocSpectrum/cross_org_research_v0/cross_org_section_extremes_v0.csv`
- `E:/output/DocSpectrum/cross_org_research_v0/cross_org_neighbors_v0.json`

Cross-pair section extremes:

| section | cross median | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: |
| АР | 0.0549 | 0.0579 | 0.0592 | 0.0602 |
| ИОС5.1 | 0.1023 | 0.1132 | 0.1149 | 0.1157 |
| ИОС5.4.1 | 0.0381 | 0.0636 | 0.0832 | 0.1196 |
| ИОС5.5.1 | 0.0469 | 0.0577 | 0.0583 | 0.0601 |
| КР | 0.0650 | 0.0744 | 0.0751 | 0.0767 |
| ПОКР | 0.0114 | 0.0127 | 0.0127 | 0.0129 |
| ПОС | 0.0294 | 0.0594 | 0.0623 | 0.0650 |
| СМ | 0.0587 | 0.1443 | 0.1468 | 0.1515 |

Interpretation:

- No cross-organization pair reaches within-organization similarity levels.
- `СМ` has the highest cross tail (`max=0.1515`), but the signal is almost
  entirely textual (`text_segment/text_word_shingle`); table layout/content and
  page signature remain zero in the top tail.
- `ИОС5.4.1` has the most interesting non-estimate tail among engineering
  sections (`max=0.1196`), with small table-layout overlap, but still far below
  within-cohort medians.
- Top pairs are concentrated around a small number of documents, which suggests
  shared normative wording or packaging effects rather than a single strong
  cross-organization borrowing event.
- The current nearest-neighbor evidence strengthens Axis C separation: the
  nearest cross-neighbor is still distant.

## Page-Level Check

The first page-level check used exact `page_signature` matches and coarse
title-page structural buckets across the combined RSPK35 + NK34 corpus.

Results:

- exact cross-organization `page_signature` matches: `1` signature;
- the only exact shared page signature is trivial: image-only page
  (`elements=1`, `text=0`, `tables=0`, `images=1`);
- no exact cross-organization structural keys were found for page `1` or page
  `2`;
- no coarse cross-organization title-page keys were found for page `1` or page
  `2`, even after reducing the key to page size + binned counts of text, lines,
  frames, images and tables.

Within-cohort title structures are stable but different:

- RSPK page 1/2 is dominated by title pages with frames and tables;
- NK page 1/2 is dominated by title pages with frames/images but no tables;
- this means cover/title pages are useful for organization/package style, but
  they are not yet a cross-organization bridge in this corpus.

Interpretation:

- We do not currently see a widely reused page-level diagram across RSPK and NK
  through exact page signatures.
- The current exact page signature is too strict for near-same diagrams; future
  `page-bucketing` or visual/vector signatures are still needed.
- Title pages support Axis C separation: both organizations have stable
  internal packaging patterns, but their structural title-page patterns differ.

## Next Research Steps

- Separate organization handwriting from title/section formatting style and
  object-series effects.
- Add a performance option to avoid writing full per-pair JSON when only
  aggregate research tables are needed.
- Decide which subset of this research should become the next review packet.
