# Source-lineage fixtures v0

## Status

Phase-0 design accepted by the human owner on 2026-06-29. This build prepares the second validation file group only; retrieval metrics and threshold calibration are not yet run.

Output:

`E:\output\DocSpectrum\source_lineage_fixtures_v0`

## Contents

- 16 canonical source PDFs: 8 text + 8 table families;
- 104 query PDFs: 48 text + 56 table variants;
- 120 unique PDF SHA-256 values;
- 85 unique content SHA-256 values because canonical, exact, and formatting-only fixtures intentionally share content;
- 10 calibration families and 6 sealed evaluation families;
- synthetic content only; no project-document text is persisted.

The exact query PDF is byte-distinct from its canonical source. A hashed instance token is stored only in PDF metadata to prevent CRC-based bundle deduplication. It is not printed on the page and must not be used by extraction or retrieval scoring.

## Generation

Use a PyMuPDF environment and an explicit Cyrillic font:

```powershell
E:\repos\pdf-structure-explorer\backend\.venv\Scripts\python.exe `
  tools\build_source_lineage_fixtures_v0.py `
  --font-file C:\Windows\Fonts\arial.ttf `
  --output-dir E:\output\DocSpectrum\source_lineage_fixtures_v0 `
  --assert-reference
```

The manifest records plan, font, content, and PDF hashes. Repeated local builds with the same plan, renderer, and font produced identical hashes for all 120 rows.

## Claim boundary

The files provide component-lineage ground truth before extraction. They do not establish borrowing, authorship, semantic paraphrase performance, graphics performance, or realistic full-document mixing.

## Next execution boundary

Run PDF Structure Explorer in three terminating batches of no more than 40 one-page fixtures. Do not place these fixtures in the production object corpus or the common training library. Their explorer bundles and retrieval artifacts must use a dedicated benchmark output namespace.

