# Text element library v0

## Purpose

This checkpoint extends the consumer-facing library beyond table forms into
the text layer. It adds exact-hash text candidates and section-level text
coverage, while staying deliberately conservative:

```text
exact text coverage != semantic originality
exact cross-org text != proven borrowing
```

The layer supports HC-010 UC1a/UC1v more broadly than the table-only report,
but it is still a hash-frequency baseline, not final semantic authorship
analysis.

## Tool

```powershell
python E:\repos\DocSpectrum\tools\build_text_element_library_v0.py `
  --base-dir E:\output\DocSpectrum\element_base_v0_rpsk35_nk34 `
  --export-root E:\output\DocSpectrum\export_rpsk35_nk34_object_view `
  --output-dir E:\output\DocSpectrum\text_element_library_v0 `
  --cohort RSPK=E:\output\DocSpectrum\export `
  --cohort NK=E:\output\DocSpectrum\export_nk_34_object_view `
  --min-objects 3 `
  --max-evidence-per-candidate 20 `
  --copy-review-max-section-df-ratio 0.25
```

Outputs:

- `text_element_candidates_v0.csv`;
- `text_element_candidate_evidence_v0.csv`;
- `text_element_section_coverage_v0.csv`;
- `text_element_library_v0.json`.

Raw text is not written. Evidence rows contain hashes and locations only.

## Candidate Rules

v0 promotes exact text hashes repeated in at least 3 distinct objects:

- `text_segment` - primary interpretable text fragment signal;
- `text_word_shingle` - phrase-reuse signal based on 5-token shingles.

Short `text_segment` candidates are retained but marked as
`diagnostic_trivial`.

Candidate classes:

- `org_text_pattern` - exact text appears only inside one cohort;
- `normative_text` - exact text is common across cohorts;
- `cross_org_text_bridge` - exact cross-org text exists, is not common enough
  by organization balance, and is rare enough inside the section to deserve
  UC3 review.

For UC3, `cross_org_text_bridge` gets `uc3_signal_status =
copy_review_needed`, not `borrowing_candidate`. This is intentionally cautious:
project documentation contains many normative and boilerplate text fragments.
Frequent cross-org text is overridden to `normative_text` even when its
organization distribution is slightly unbalanced.

## Run Summary

The first run on RSPK35 + NK34 produced:

```text
documents: 474
candidates: 43 740
evidence rows: 598 437
coverage rows: 474
skipped groups below min_objects: 46 636
copy-review max same-section DF ratio: 0.25
```

Evidence is sampled per candidate (`max_evidence_per_candidate = 20`); full
occurrence counts remain in candidate rows. The sample is cohort-aware so a
cross-org candidate exposes evidence from both sides when available.

Candidate kinds:

```text
text_segment       27 865
text_word_shingle  15 875
```

Candidate classes:

```text
org_text_pattern        36 355
normative_text           7 135
cross_org_text_bridge      250
```

Candidate statuses:

```text
candidate           26 707
diagnostic_trivial  17 033
```

## Coverage Results

Median `text_segment` coverage by section:

```text
АР        0.4464
ИД        0.3986
ИОС5.1    0.2902
ИОС5.4.1  0.3723
ИОС5.5.1  0.1779
КР        0.4517
ПОКР      0.6039
ПОС       0.3101
СМ        0.2457
```

Median `text_word_shingle` coverage is very high across sections
(`~0.97-0.997`). This is useful as a phrase-reuse signal but too saturated to
serve as a clean originality metric by itself.

Median `text_segment` coverage by cohort:

```text
NK    0.3612
RSPK  0.3174
```

The initial no-rarity version over-flagged cross-org bridges because many
near-universal boilerplate phrases had slightly unbalanced organization ratios.
After the rarity guard:

```text
cross_org_text_bridge candidates: 250
documents with copy_review_needed occurrences: 123 / 474
max copy_review_needed occurrences in one document: 52
documents with foreign_org_text_ratio > 0.05: 68 / 474
```

Interpretation:

- the text layer is much denser than table forms;
- exact text bridges are expected in normative/boilerplate documentation;
- rare cross-org bridges are review signals, not proof of copying;
- text coverage helps UC1a/UC1v, but final conclusions need IDF weighting,
  near-match and semantic layers.

## Product Meaning

This layer broadens the first consumer-facing report:

- table coverage shows reusable structured forms;
- text-segment coverage shows recurring textual fragments;
- shingle coverage highlights phrase-level reuse but is boilerplate-prone;
- residual means unexplained by the v0 exact-hash text library, not proven
  original authorship.

Headline product coverage should use `text_segment` first. `text_all` is useful
as a combined diagnostic but is inflated by saturated shingle coverage.

The safe product wording for v0:

```text
Known text coverage / unexplained text residual / cross-org text bridges for review
```

not:

```text
copied / original / author proven
```

## Known Limits

- Exact text hashes are brittle to small edits.
- Shingle coverage is highly saturated.
- `cross_org_text_bridge` has a rarity guard, but still needs normative
  filtering and near-match context.
- No embeddings or semantic similarity are used.
- Evidence is sampled, not exhaustive.
- Encoding issues in source PDFs can affect text hashes; this remains a known
  corpus quality risk.

## Next Steps

- Add IDF-weighted text coverage so boilerplate has less influence.
- Split text candidates into user-facing tiers: normative, org-pattern,
  review-signal, diagnostic.
- Combine table and text coverage into one section library-coverage report.
- Add near-match before treating text bridges as UC3 evidence.
