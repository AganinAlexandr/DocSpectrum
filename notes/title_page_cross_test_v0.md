# Title page cross-test v0

## Purpose

This checkpoint reuses the validated Checker title-page detector output as an
external DocSpectrum eval/profile input. It does not add title-page semantics
to the PDF core.

The test asks:

- do title-page element spectra separate project organizations;
- does the signal survive comparisons across different section types;
- is the title surface a cleaner organization/GIP probe than body pages;
- does the result survive removal of page size as a possible confound.

Current ground truth covers organization only. GIP-level conclusions require
GIP labels.

## Inputs

Title labels joined by CRC32:

- RSPK: `registries/title_pages_by_crc.csv`;
- NK: `projects/docspectrum/inputs/title_pages_nk_v0.csv`.

Page features:

- `element_base_v0_rpsk35_nk34/page_signatures_v0.csv`;
- `element_base_v0_rpsk35_nk34/documents_index.csv`.

Coverage:

```text
documents: 475
title_anchor profiles: 475
cover_zone profiles: 475
body profiles: 475
missing reference: 0
non-high reference: 0
missing profile: 0
```

## Tool

```powershell
python E:\repos\DocSpectrum\tools\build_title_page_cross_test_v0.py `
  --base-dir E:\output\DocSpectrum\element_base_v0_rpsk35_nk34 `
  --output-dir E:\output\DocSpectrum\title_page_cross_test_v0 `
  --cohort RSPK=E:\output\DocSpectrum\export `
  --cohort NK=E:\output\DocSpectrum\export_nk_34_object_view
```

Scopes:

- `title_anchor`: detected title pages;
- `cover_zone`: all front-matter pages through `cover_end`;
- `body`: all pages after the cover zone.

## Similarity

The title element spectrum uses domain-neutral page features:

- text count;
- line count;
- frame count;
- image count;
- table count;
- residual other-element count.

`title_element_similarity_v0` combines:

- per-page feature-ratio similarity;
- element-composition overlap;
- page-size overlap.

Because page size itself strongly separates the two current organizations, the
tool also reports:

```text
title_element_similarity_no_size_v0
```

This sensitivity metric removes page-size overlap entirely.

Exact page-signature Jaccard is diagnostic only because exact hashes remain too
strict.

## Organization Spectra

Median title-anchor spectrum:

```text
cohort  title pages  elements/page  text  frames  images  tables
NK      2            24             19.5  1       3       0
RSPK    2            30             24.5  3       1.5     1
```

This confirms the earlier RP-015 observation:

- NK titles are image-heavier and table-free;
- RSPK titles contain more frames and tables.

## Main Result

No-size median similarity:

```text
scope         pair type   section relation   median
title_anchor  within_org  different_section  0.9490
title_anchor  cross_org   different_section  0.5802
title_anchor  within_org  same_section       0.9846
title_anchor  cross_org   same_section       0.5879

body          within_org  different_section  0.5041
body          cross_org   different_section  0.3687
body          within_org  same_section       0.9123
body          cross_org   same_section       0.4345
```

Separation gaps:

```text
title_anchor, different section: 0.3688
title_anchor, same section:      0.3967
body, different section:        0.1354
body, same section:             0.4778
```

Interpretation:

- body pages strongly identify organization when the same section is compared,
  but much of that signal is entangled with section type;
- title pages retain a large organization gap even across different sections;
- therefore title pages are a cleaner organization-template probe than body
  pages for cross-section comparison.

## Nearest Neighbors

For both with-size and no-size metrics:

```text
title_anchor nearest neighbor within organization: 475 / 475
cover_zone nearest neighbor within organization:   475 / 475
body nearest neighbor within organization:         475 / 475
```

No-size nearest-neighbor section relation:

```text
scope         different section  same section
title_anchor  203                272
cover_zone    204                271
body           19                456
```

This is the strongest qualitative result:

- body nearest neighbors almost always come from the same section;
- title nearest neighbors often come from different sections of the same
  organization;
- title structure therefore carries an organization-wide pattern beyond the
  individual section template.

## Page-Size Sensitivity

Page-size Jaccard is:

```text
within organization median: 1.0
cross organization median:  0.0
```

This is a real current-corpus signal but could reflect software/export/template
settings. It is not required for the result:

- all 475 no-size nearest neighbors still stay within organization;
- the cross-section title gap remains `0.3688` without page size.

## Exact Signatures

Exact title page-signature overlap is rare:

- cross-organization exact matches: `0`;
- within-organization same-section pairs with positive exact overlap: `52`;
- median exact Jaccard remains `0`.

This confirms that near-match remains necessary. The useful organization signal
comes from element spectra, not exact page hashes.

## Outputs

- `title_page_profiles_v0.csv`;
- `title_page_pairs_v0.csv`;
- `title_page_similarity_summary_v0.csv`;
- `title_page_nearest_neighbors_v0.csv`;
- `title_page_cross_test_v0.json`.

Output directory:

```text
E:\output\DocSpectrum\title_page_cross_test_v0
```

## Boundaries

- This is a profile/eval test over the universal PDF feature core.
- It validates organization separation for RSPK vs NK, not all organizations.
- It does not yet validate GIP attribution.
- Body comparisons remain section-confounded.
- The combined title metric is experimental and not a product score.
- Near-match is still required for UC3 and correlated-organization cases.
