# crc export linkage v0

DocSpectrum follows shared `DEC-20260615-006`:

`source PDF crc32 -> doc_<lower(crc32)> -> pdf-structure-explorer export bundle`

## Rule

- Compute `crc32` from the original source PDF bytes.
- Resolve the explorer export folder as `doc_<lower(crc32)>`.
- Verify the selected export folder through `documents.csv`:
  - `file_crc32` must match the source PDF CRC32;
  - `file_name` should be used as a diagnostic, not as the primary key.
- Keep domain identity separately:
  - `object_id`, address, designer and subgroup come from the project manifest;
  - `doc_<crc32>` is the document/bundle identity.

This avoids unstable filename matching and survives parallel mutation of shared
export folders.

## NK-34 Check

Generated artifacts:

- `E:/output/DocSpectrum/crc_export_linkage_nk_34/source_pdf_crc_v0.csv`
- `E:/output/DocSpectrum/crc_export_linkage_nk_34/export_documents_crc_v0.csv`
- `E:/output/DocSpectrum/crc_export_linkage_nk_34/doc_crc_linkage_v0.csv`
- `E:/output/DocSpectrum/crc_export_linkage_nk_34/doc_crc_linkage_v0.json`

Current result:

- manifest objects: `34`
- source PDFs scanned: `789`
- source unique CRC32: `691`
- export documents: `196`
- export unique CRC32: `196`
- matched export documents: `196`
- matched objects: `34`
- export-only documents: `0`
- `doc_<crc32>` folder mismatches: `0`

Interpretation:

- The `НК-Инжениринг` explorer export set is fully linked to source PDFs.
- `source_only=593` is expected because source project folders contain more PDFs
  than were exported for the current DocSpectrum run.
- The next processing layer can use `doc_crc_linkage_v0.csv` as the bridge from
  `object_id` to `doc_<crc32>` bundles.
