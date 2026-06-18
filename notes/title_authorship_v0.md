# Title authorship extraction v0

## Scope

The layer extracts organization/GIP parties from one representative section
per object. It consumes the shared Checker title-zone detector and adds a
DocSpectrum-only OCR adapter for bundles classified as `image_title`.

The shared detector remains unchanged.

## Corpus result

For the 46-object priority GIP corpus:

- 46/46 title structures recovered;
- all selected sections contain two title pages;
- no four-title subcontractor structure occurs in this selected `KR` corpus;
- 22 documents use the text layer;
- 24 raster/image title blocks use Tesseract CLI recovery;
- 46/46 organizations extracted;
- 46/46 GIP surnames extracted.

OCR evidence is retained separately from the cleaned organization name.
Ambiguous candidates remain reviewable.

## Reconciliation

`gip_reconciliation_v0` compares title evidence to the planned experimental
labels without silently overwriting either source:

- 35 exact GIP matches;
- 2 OCR-near matches (`Sergeeb` versus `Sergeev` after transliteration);
- 9 source conflicts requiring owner review;
- 45 organization matches;
- 1 organization conflict (`1690_25`: planned StroyMontazh, title Vitmar).

The nine GIP conflicts are:

- `1667_25`, `1668_25`, `1678_25`, `1873_25`, `1874_25`, `1875_25`,
  `1876_25`: planned Borodin, title GIP Loktev;
- `1692_25`: planned Shevchenko, title GIP Loktev;
- `1690_25`: planned Efimov, title GIP Savchenkov.

These are data-source conflicts, not automatically parser errors. The title
evidence and planned labels remain side by side until owner resolution.

## Outputs

- `E:/output/DocSpectrum/title_authorship_v0`;
- `E:/output/DocSpectrum/gip_reconciliation_v0`.
