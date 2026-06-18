# GIP PDF selection v0

## Purpose

Select one comparable analysis section per priority object and prepare a flat
input set for PDF Structure Explorer.

## Source roles

- `analysis_target_pdf`: `КР` for all 46 factor-test objects;
- `authorship_source_pdf`: one representative section selected by priority
  `КР -> ПОКР/ПОС -> АР`.

All organization/GIP parties found on the selected title pages are retained,
including subcontractors in a four-title structure.

## Selection

The target selector requires an independent `КР` marker and excludes:

- `ИУЛ`;
- `ПОКР`.

Result:

- 45 objects have exactly one target `КР`;
- `1825_25` has five distinct versions;
- for `1825_25`, the pre-expertise version from
  `01_Документация на проверку` is selected;
- all five versions remain in the version inventory.

Explicitly confirmed pre-expertise source directories:

- `1823_25`: `01_Документация на проверку/Документация на проверку`;
- `1825_25`: `01_Документация на проверку`.

## Outputs

Generated under `E:/output/DocSpectrum/gip_pdf_selection_v0`:

- `gip_pdf_selection_v0.csv`;
- `gip_pdf_versions_v0.csv`;
- `gip_pdf_selection_v0.json`.

Explorer staging:

`E:/output/DocSpectrum/gip_priority_analysis_pdf_input_v0`

Each staging filename contains:

```text
object_id__KR__crc32.pdf
```

Source files are never moved or modified.

When the authorship source is the same `КР`, its staging copy is reused. A
separate authorship staging copy is created only for fallback `ПОКР/ПОС/АР`.

Batch explorer runner:

`tools/run_explorer_gip_batch_v0.py`

It uses the explorer parser/exporter directly, skips complete existing exports
by CRC32 and writes a status row after every document.
