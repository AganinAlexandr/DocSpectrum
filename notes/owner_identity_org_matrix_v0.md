# Owner-identity organization matrix v0

## Purpose

This is the first consumer-facing identity layer built on the validated
DocSpectrum library. It does not determine an owner or author absolutely.
It finds organization links relative to the current library and keeps the
signals separate:

1. blind handwriting similarity over authorial PDF content;
2. shared GIP;
3. disclosed four-title lead/subcontractor network;
4. temporal handoff from `дата_вх`.

IUL personnel rosters are not used as model features. They remain future
validation ground truth under HC-015.

## Corpus and comparison

- canonical authorial documents: `1032`;
- homogeneous `work type x section` cells: `44`;
- all document pairs: `26182`;
- organization pairs with at least one comparable cell: `696`;
- sections: `АР`, `КР`, `ПОС`, `СМ`;
- provenance-first third-party subtraction is applied before aggregation.

Only documents in the same work type and section are compared. Organization,
GIP, title-network, and temporal labels are joined after similarity scoring.

## Memory-safe execution

The tool processes one homogeneous cell at a time and releases its document
profiles before moving to the next cell. The largest cell contained `5671`
pairs; the full run stayed near `0.15 GB` Python working set.

## Calibration finding

The H2 transfer thresholds cannot be reused directly for owner clustering.
Size-invariant structural composition is high for most cross-organization
cells:

- cross-org structural-composition p90: about `0.977`;
- cross-org residual-shingle p95: `0.1690`;
- cross-org residual strong-share p95: `0.5719`.

Using H2 retention alone produced `446/696` candidate edges and one giant
component. That graph was rejected as non-discriminative.

The owner-identity graph therefore uses:

- at least `2` supported homogeneous cells;
- residual shingle and residual strong-share both in the cross-org p95 tail;
- or an independently disclosed four-title lead/subcontractor edge.

Structure remains an explanatory channel, but does not create an owner link by
itself.

## Result

- candidate graph edges: `12`;
- connected candidate components: `5`.

The components are research candidates, not owner verdicts:

1. `АО ССУ № 3 | Комтех | Сфера`;
2. `Ватага | ИнфраСтройИнтекс | СП Стройинвест ГРУПП | Спектр`;
3. `Горизонт | ЛСТехникс | СВАЙТЕК-М | ТрансРегионСервис | Экономный Дом`;
4. `Мир | ООО К1`;
5. `РусСтройГрупп | СитиГазСтрой`.

These require independent validation. A component can represent a common
owner, a production network, shared templates, or another correlated process.

## Anchor validation

### Confirmed rename: Комтех -> АО ССУ № 3

Reproduced.

- comparable cells: `4` (`фасад`, `АР/КР/ПОС/СМ`);
- document pairs: `36`;
- residual shingle absolute median: `0.4662`;
- residual strong-share absolute median: `0.8372`;
- shared GIP: `питанов`;
- temporal handoff direction: `Комтех -> АО ССУ № 3`;
- handoff boundary: `2025-Q1`.

The handwriting, GIP, and temporal channels independently point in the same
direction.

### Disclosed network: Ватага <-> Спектр

Reproduced as a production-network edge, not as a handwriting-copy edge.

- disclosed four-title objects: `17`;
- comparable cells: `4`;
- residual shingle absolute median: `0.0101`;
- residual strong-share absolute median: `0.0`.

This distinction is important: the title network is real, while the current
authorial residual does not claim the two organizations have the same text
handwriting.

### Known owner pair: Тиволион <-> ООО К1

Not testable in v0. The organizations do not share a homogeneous
`work type x section` cell in the current canonical document set. This is a
coverage gap, not negative evidence, and directly demonstrates HC-016:
DocSpectrum conclusions are relative to the available library.

## Interpretation boundary

- `candidate` means worth investigating within the current library;
- a component is not proof of common ownership;
- disclosed subcontracting is not falsification;
- temporal handoff is corroborating evidence, not an identity decision;
- future IUL harvest must validate the graph without feeding personnel labels
  back into its construction.
