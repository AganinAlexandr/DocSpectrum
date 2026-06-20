# IUL personnel validation v0

## Purpose

This layer uses historical information-certification sheets (ИУЛ) only as
external validation for the eight `owner_or_template_candidate` edges from
RP-040.

IUL personnel is not fed into handwriting scoring or graph construction.
The goal is to test whether a durable content-handwriting method correlates
with historical declared personnel links.

In this capital-repair corpus, IUL rosters are a noisy and potentially formal
source. Project staff could fill them on a "just submit it" basis. Developer
names are therefore weak declared labels, not ground truth. The title-page GIP
is the authoritative section-title reference, but is not required to appear in
a properly formed IUL roster. If present, the same engineer may legally be
listed there in another role such as developer.
Detached signature metadata is not read in this layer, so the actual
cryptographic signer is not verified here.

## Input boundary

- target organizations: `12`;
- target objects: `224`;
- target handwriting edges: `8`;
- files read: only IUL `*.pdf`;
- detached `*.sig`: excluded completely (`0` read).

The filename must have a strict `.pdf` extension and an IUL/UIL marker.
Files such as `ИУЛ_АР.pdf.sig` are not candidates.

## Privacy

No raw names or IUL text are written to artifacts.

- normalized full person key -> SHA1;
- normalized surname -> separate SHA1;
- role class remains readable (`developer`, `gip`, `control`, `approved`);
- exact-person and surname-only overlap are reported separately.

Surname overlap is a weak review signal and cannot replace exact overlap.

## Extraction

- IUL PDF files found: `1037`;
- unique PDF contents: `1033`;
- text-layer PDFs parsed: `1020`;
- image-only scanned IUL: `13`;
- duplicate contents skipped: `4`;
- person-role hash evidence rows: `3809`.

Explicit MuPDF object destruction and store cleanup are required. Without
cleanup, the first run exhausted the WASM store after 548 files even though
the remaining PDFs were individually valid.

The 13 image-only files belong to:

- `Горизонт`: `3`;
- `СитиГазСтрой`: `10`.

They need a separate OCR route and are not silently interpreted as empty
rosters.

## Validation results

### Descriptive title-page GIP presence in IUL

The title page is authoritative for who is shown as GIP for the section.
The IUL roster does not have to contain that person when other required names
are properly provided. Presence, another role, or absence are therefore
descriptive cross-document states, not correctness statuses. A qualified
engineer may legally appear as a simple developer; the IUL role does not have
to equal the title role.

Detached `.sig` files are not read, so this compares PDF-declared rosters, not
the cryptographic certificate owner.

Object-level result for `224` target objects:

- title-page GIP appears as IUL `ГИП`: `152`;
- title-page GIP appears in another IUL role: `2`;
- title-page GIP not observed in the extracted IUL roster: `1`;
- title-page GIP reference unavailable: `60`;
- image-only IUL needing OCR: `3`;
- no IUL PDF: `6`.

Among the `155` directly comparable objects, the title-page GIP appears
somewhere in the IUL roster in `154` cases (`99.4%`).

- `1059_24`, АО ССУ № 3:
  - title-page GIP: Питанов;
  - IUL role `ГИП`: Жиров;
  - Питанов appears in IUL as `Разработал`.
- `1070_24`, АО ССУ № 3:
  - the same role split: title-page GIP Питанов, IUL GIP Жиров, developer
    Питанов.

These two configurations are not violations: the title-page GIP is present in
the IUL roster and may also act as a developer.

One object illustrates the third descriptive state:

- `1366_25`, Сфера:
  - title-page GIP: Шпаков;
  - all five IUL PDFs list Жиров as `ГИП`;
  - all five list Питанов as `Разработал`;
  - Шпаков is absent from the extracted rosters.

This is not an error or review candidate by itself. It demonstrates why title,
IUL roster, content handwriting, and future UKEP metadata must remain separate
evidence channels.

At file level:

- readable IUL PDFs with an extracted GIP role: `1009 / 1020`;
- readable IUL PDFs without an extracted GIP role: `11`.

The latter count is a document-format/QC signal and is not automatically
treated as misconduct.

### Weak declared developer overlap

#### Комтех <-> Сфера

- developer sets: `2 / 2`;
- shared developers: `2`;
- developer Jaccard: `1.0`;
- shared GIP: `1`.

The handwriting attachment has a matching declared developer roster. Because
non-GIP names in IUL may be formal or inaccurate, this is weak corroboration,
not independent proof of a shared team or common ownership.

#### АО ССУ № 3 <-> Сфера

- developer sets: `1 / 2`;
- shared developers: `1`;
- developer Jaccard: `0.5`;
- shared GIP: `1`;
- all-roster shared: `2`.

Historical declared personnel overlap exists, so generic template noise is not
the only possible explanation. The roster is noisy, and the link remains
outside the confirmed Komtekh->SSU rename core.

#### Мир <-> ООО К1

- developer sets: `4 / 2`;
- shared developers: `1`;
- developer Jaccard: `0.2`;
- shared GIP: `0`.

This is weak evidence of a personnel/production connection independent of a
shared GIP. It is useful for review of the wider known owner cluster around
K1/Tivolion, but does not close the current Tivolion-K1 coverage gap.

### No declared personnel overlap in current IUL

- `ЛСТехникс <-> ТрансРегионСервис`;
- `СВАЙТЕК-М <-> Экономный Дом`;
- `ТрансРегионСервис <-> Экономный Дом`.

All have readable IUL coverage on both sides but no exact or surname overlap
across developer, GIP, control, approved, or all-roster sets. Given the weak
quality of non-GIP IUL rosters, this does not meaningfully disprove shared
personnel and must not automatically shift the relation toward a
template-only explanation.

### Insufficient without OCR

- `Горизонт <-> Экономный Дом`;
- `РусСтройГрупп <-> СитиГазСтрой`.

The Horizon and CityGazStroy IUL PDFs are image-only. These edges stay
unassessed until an explicit OCR pass.

## Interpretation

Among eight ambiguous handwriting edges:

- `3` have matching declared developer names (weak corroboration);
- `3` have no declared personnel overlap, which is not dispositive;
- `2` remain insufficient because one side is image-only.

The primary additional value is empirical comparison of the durable
handwriting graph with declared rosters. Title-page GIP presence is retained
only as descriptive context.

IUL is historical and falsifiable. Agreement with a non-GIP name weakly
corroborates a hypothesis; disagreement may reflect poor IUL filling and does
not weaken the handwriting result by itself.
