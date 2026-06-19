# Org alias registry v0

## Purpose

Title extraction already identifies organizations, but OCR and letterhead noise
split one legal entity into several variants. This layer builds a reviewable
alias registry before any organization-level handwriting experiment.

It is intentionally conservative:

- no hidden overwrites of title evidence;
- canonical names are hints, not irrevocable truth;
- raw variants remain preserved for audit.

## Inputs

The builder scans all available `title_authorship_range_*_results_v0`
directories and reads `title_authorship_parties_v0.csv`.

When `E:/commons/DocSpectrum/Капремонт_Объекты.xlsx` is available, the first
pass also reads the canonical organization columns:

- `проектировщик`;
- `генПодрядчик`.

If one of them matches the title-derived identity hint for an object, the alias
registry prefers that display name over the most common OCR variant.

The registry never overrides title-page role structure:

- title pages remain the source of truth for lead versus subcontractor;
- `генПодрядчик` only helps normalize the organization name of the first title
  pair when that pair already exists in title evidence;
- `проектировщик` only helps normalize the real executor name, especially for
  subcontractor pages 3+.

## Outputs

- `org_alias_registry_v0.csv`:
  one row per identity-hint group;
- `org_alias_variants_v0.csv`:
  one row per raw observed variant inside a group.

The first pass groups by:

- quoted organization name when present;
- legal-form hint (`ООО`, `АО`, `ПАО`, ...);
- extra homoglyph cleanup for OCR variants such as `ɋɬɪɨɣ Ɇɨɧɬɚɠ ɋɉ`.

## Use

This registry is the staging layer before:

- organization-level conformance experiments;
- GIP-control on organization-authored residual;
- manual approval of stable canonical organization identities.
