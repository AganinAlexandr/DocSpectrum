# Typical element candidates v0

## Purpose

This checkpoint starts the first consumer-facing library layer: not just a
catalog of extracted entities, but candidates that can explain what part of a
section is covered by known typical forms and how organization-specific these
forms are.

The v0 scope follows the shared T-016 / HC-010 direction:

- build P1 coverage immediately: how recurrent a candidate is inside the
  section library;
- build P2 organization distinctiveness immediately: whether a candidate is
  common across cohorts or characteristic for one organization;
- keep the candidate row thin and put occurrence-level facts into a separate
  evidence table;
- frame the IOS5.4.1 seed as a normative table form, not as borrowing.

## Inputs

Tool:

```powershell
python E:\repos\DocSpectrum\tools\build_typical_element_candidates_v0.py `
  --base-dir E:\output\DocSpectrum\element_base_v0_rpsk35_nk34 `
  --export-root E:\output\DocSpectrum\export_rpsk35_nk34_object_view `
  --output-dir E:\output\DocSpectrum\typical_element_candidates_v0 `
  --cohort RSPK=E:\output\DocSpectrum\export `
  --cohort NK=E:\output\DocSpectrum\export_nk_34_object_view `
  --min-objects 3
```

Input artifacts:

- `element_base_v0.csv` for table layout/content signatures;
- `table_cells.csv` from explorer exports for hashed table-cell text evidence;
- cohort roots for post-extraction organization labels.

No raw text is written to the candidate artifacts.

## Candidate Rule

v0 is table-centric. One candidate is:

```text
(section_code, table_layout_signature)
```

promoted only when it is found in at least 3 distinct objects. The candidate ID
is hash-derived from the candidate scope and signature group, so it is stable
across rebuilds as long as the extraction contract is stable.

This intentionally starts from table forms because they are more structured
than plain text shingles and less strict than whole-page signatures.

## Outputs

Output directory:

```text
E:\output\DocSpectrum\typical_element_candidates_v0
```

Files:

- `typical_element_candidates_v0.csv` - thin candidate catalog;
- `typical_element_candidate_evidence_v0.csv` - per-occurrence evidence;
- `typical_element_candidates_v0.json` - run metadata and summary.

Candidate columns include:

- recurrence: distinct object/document counts and occurrence count;
- P1 coverage: object/document coverage ratios and section IDF;
- P2 organization distinctiveness: cross-org/common/specific labels, dominant
  organization, per-org object and occurrence counts;
- content variability: whether the form is paired with stable or varying table
  content;
- near-match status: currently `not_evaluated`.

Evidence rows include object, bundle, page, table id, layout/content hashes,
shape counts, bbox area, and table-cell text hashes.

## Run Summary

The first run on RSPK35 + NK34 produced:

- candidates: 531;
- evidence rows: 7485;
- skipped layout groups below `min_objects=3`: 1830;
- documents with cached table-cell hashes: 473.

Candidate counts by section:

```text
АР        21
ИД        28
ИОС5.1    86
ИОС5.4.1 183
ИОС5.5.1  74
КР        24
ПОКР      22
ПОС       22
СМ        71
```

Organization distinctiveness:

```text
cross_org_common   7
org_distinctive    2
org_specific     522
```

## IOS5.4.1 Seed

The expected cross-organization IOS5.4.1 bridge was promoted as several
`cross_org_common` table-form candidates.

The main seed family has the same table form:

```text
8 rows x 4 columns / 22 cells
```

It appears across 13 objects with this object distribution:

```text
NK:10 | RSPK:3
```

The content signatures vary, so the correct interpretation is:

```text
stable form, variable content
```

This is a typical/normative form candidate. It is not evidence of borrowing by
itself. Borrowing or shared authorship would require stronger content-level or
near-match evidence.

## Product Link

This layer directly supports the first user-facing checks:

- organization handwriting: compare a section against forms typical for the
  organization and forms common across organizations;
- employee review: separate expected template coverage from residual material
  that needs originality or authorship analysis;
- external material intake: see whether a transferred section brings familiar,
  common, or foreign forms;
- template selection: rank library sections by reusable typical forms.

The key distinction for later UI and reports:

```text
form coverage != copied content != original residual
```

Using organization templates is normal. Suspicious copying starts when the
non-template residual or content-level signatures match too strongly.

## Known Limits

- v0 uses exact `table_layout_signature`; near-match is not implemented yet.
- whole-page, vector, image, and text-only candidates are not promoted here.
- content variability is based on exact `table_content_sha1`, not near-content.
- organization labels are currently limited to RSPK and NK cohort roots.
- many `org_specific` candidates are valid diagnostics, but not all are ready
  to become user-facing library elements without ranking and review.

## Next Steps

Near-term:

- add a section coverage report: which candidates explain an input section;
- rank candidates by coverage, org distinctiveness, and content variability;
- add near-match/bucketing for table forms and then page forms.

Later:

- promote content-level candidates when content, not only form, recurs;
- add executor-level labels only when per-executor ground truth exists;
- connect candidates to comparison reports as explanations of similarity.
