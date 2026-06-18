# GIP priority corpus manifest v0

## Purpose

The manifest records the first human-approved corpus for title-based
organization/GIP extraction and later GIP handwriting experiments.

The experiment plan is preserved separately from title-derived ground truth.
XLSX values are selection metadata only; title pages are authoritative.

## Corpus design

### Scheme 1

Fixed organization and work type, varying GIP:

- pitched roof: Loktev / Efimov / Borodin;
- flat roof: Borodin / Loktev / Efimov / Shevchenko;
- expected organization: StroyMontazh.

### Cross-organization

Fixed GIP and work type, varying organization:

- Sergeev, flat roof: Vataga / Gamma / Stroyinvest;
- Sergeev, pitched roof: Vataga / Stroyinvest.

### Scheme 2

Fixed GIP, varying genuine work type on different objects:

- Sergeev: pitched roof / flat roof / facade / balconies / foundation.

Roof objects from the cross-organization scheme are reused as memberships, not
duplicated as objects.

## Counts

```text
unique objects:          46
experiment memberships: 56
```

## Current readiness

All 46 archive directories exist. At manifest build time:

- no object has an accessible target-section PDF;
- one object (`1701_25`) has only an unrelated `ИД` PDF outside the target
  work-type comparison;
- most objects contain XML + an archive or an archive only;
- `1823_25` and `1825_25` are empty directories.

The objects therefore require extraction/unpacking and explorer exports before
title organization/GIP ground truth can be collected.

## Readiness update

All 46 source directories are now unpacked and all 46 selected `KR` files have
complete explorer exports. The earlier archive-only/empty-directory state
above is historical preparation metadata.

Confirmed pre-expertise directories:

- `1823_25`: `01_Documentation/Documentation` (the nested confirmed source);
- `1825_25`: `01_Documentation` (the confirmed pre-expertise source).

Title extraction and reconciliation results are documented in
`notes/title_authorship_v0.md`.

## Known registry discrepancy

Object `1690_25` belongs to the human-designed StroyMontazh/Efimov pitched-roof
cell, while the XLSX registry currently lists organization `Витмар`.

The mismatch is intentionally retained. The title-page extractor must resolve
the actual organization and all GIPs.

## Outputs

Generated under `E:/output/DocSpectrum/gip_priority_manifest_v0`:

- `gip_priority_objects_v0.csv` — 46 unique source objects and readiness;
- `gip_priority_memberships_v0.csv` — 56 experiment memberships;
- `gip_priority_manifest_v0.json` — counts, rules and discrepancies.

## Ground-truth rule

Authorship extraction and handwriting analysis use separate source roles:

- `authorship_source_pdf` - one representative section selected by priority
  `КР -> ПОКР/ПОС -> АР`;
- `analysis_target_pdf` - the comparable section used in the factor experiment
  (`КР` for the current roof/facade/balcony/foundation corpus).

Normally the selected `КР` serves both roles. If `КР` is absent, authorship
metadata comes from `ПОКР/ПОС`, then `АР`, without removing the object from the
GIP corpus.

For every selected object:

1. run the shared title-zone detector;
2. extract all organization/GIP pairs from detected title pages;
3. preserve lead and subcontractor roles;
4. assign effective author to the subcontractor GIP when subcontracting is
   confirmed;
5. compare title-derived values to XLSX only as data-quality diagnostics.
