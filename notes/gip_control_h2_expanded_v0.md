# GIP-control H2 expanded corpus v0

## Scope

The expanded H2 experiment combines the non-UUiR corpora for objects
`1001-1883`.

- objects in the merged manifest: `577`;
- complete explorer section bundles: `2133`;
- resource exclusions: `3` (`1196_24` AR; `1220_24` AR/KR);
- canonical organizations after human audit: `54`;
- objects with an organization: `563`;
- objects ready for GIP control (`GIP + organization`): `420`;
- subcontractor-authored objects: `33`.

The headline calculation excludes:

- `PZ`, `ID`, `UNKNOWN`;
- temporary filename class `ENGINEERING`;
- working-documentation class `GVS`.

The scored authorial section classes are `AR`, `KR`, `POS`, and `SM`.

## Pipeline

1. Expanded manifest/selection merge with complete-bundle guard.
2. Title-derived GIP/organization registry with alias canon.
3. Human organization audit.
4. Size-invariant baseline.
5. Page near-match.
6. Expert-calibrated third-party provenance subtraction.
7. Equal-weight matched-cell H2 summary.
8. Old-to-expanded replication and minimum pair-support assessment.

## Volume

- ready known-section rows: `1084`;
- document profiles: `374`;
- pairwise rows: `1618`;
- H2 pairs: `373` (`156` same-org / `217` cross-org);
- H2 matched cells: `19` (previous corpus: `12`);
- supported H2 cells with at least `3` same-org and `3` cross-org pairs: `13`;
- GIPs with matched cells: `4`.

## H1 control

The expanded corpus preserves the positive within-organization GIP signal after
third-party subtraction:

| Metric | Same GIP | Different GIP |
|---|---:|---:|
| residual page near shingle median | 0.3942 | 0.0508 |
| residual strong-share median | 0.8404 | 0.1976 |

The authorial signal remains strong before interpreting H2.

## H2 findings

### Sergeev

Status: `transfer_supported`.

- supported cells: `6/6`;
- median style-composition retention: `0.9999`;
- median strong-share retention: `0.9627`;
- organizations: Vataga, Gamma, SK Granit, SP Stroyinvest Grupp.

Four cells transfer both structure and content; two are structure-led with
partial content retention. The earlier cross-organization finding replicates
and broadens from pitched roofs to flat roofs.

### Ruzaev

Status: `content_org_bound_structural_residue`.

- supported cells: `3/3`;
- median style-composition retention: `0.7722`;
- median strong-share retention: `0.0000`;
- organizations: SK Vector, StroyMontazh SP.

All three flat-roof sections retain some structural similarity, but authorial
content does not transfer across organizations. The earlier organization-bound
interpretation is now supported by `16` same-org and `20` cross-org pairs per
section.

### Shiryaev

Status: `mixed_by_section`.

- supported cells: `3/6`;
- median style-composition retention: `1.0751`;
- median strong-share retention: `0.5769`;
- organizations include Vataga, InfraStroyIntex, MSK Grupp, GK Imperiya, and
  DaVinci Company.

Flat-roof `POS` transfers both channels; flat-roof `KR` is structure-led; the
water-supply `POS` cell is content organization-bound. Pitched-roof cells still
have insufficient same-org support.

### Korneeva

Status: `structure_transfer_content_mixed_preliminary`.

- supported cells: `1/4`;
- organizations: OOO Stroyrazvitie, Stroyrazvitie M, OOO TLC.

Only `heating x POS` meets the minimum pair support (`9` same-org / `12`
cross-org). It is structure-led with partial content retention. Balcony cells
look transferable but have only one same-org pair and remain insufficient.

## Replication

- old matched cells: `12`;
- expanded matched cells: `19`;
- directly persisted status: `4`;
- support changed from insufficient to supported: `8`;
- new cells: `7`.

The main value of expansion is not a larger pooled score. It converts several
previously anecdotal one-pair cells into supported comparisons and exposes
section-specific transfer behavior.

## Interpretation boundary

The experiment supports a GIP-specific transfer model:

- a GIP can carry both structural and content signature across organizations;
- another GIP can retain only a structural residue while content remains
  organization-bound;
- transfer can vary by work type and section.

These are research signals, not legal authorship or borrowing conclusions.
