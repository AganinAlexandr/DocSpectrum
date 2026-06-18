# Title authorship range 1800-1883 v0

## Scope

The range corpus covers every object directory from `1800_25` through
`1883_25`. One representative authorship section is selected by priority:

```text
KR -> POKR -> POS -> AR
```

`IUL` files are excluded. Every selected PDF is keyed by CRC32 and processed
through PDF Structure Explorer before title-party extraction.

## Result

- expected objects: 84;
- source directories: 84;
- selected PDFs: 83;
- unique CRC32 values: 83;
- selected sections: 79 `KR`, 4 `POKR`;
- explorer failures: 0;
- title parties: 84 across 83 documents;
- two-title documents: 82;
- four-title documents: 1.

The remaining unavailable object is `1846_25`, whose directory currently has
no PDF files.

## Subcontractor case

Object `1869_25` contains four title pages. Pages 3-4 identify the effective
subcontractor:

- organization: `Спектр`;
- GIP: `Егупов В. В`.

## Incremental addition

Object `1830_25` became available after the first range run and was added
without rerunning Explorer for the other objects:

- section: `KR`;
- organization: `ООО ВИТМАР`;
- GIP: `Савченков В.М`.

## Outputs

- selection and inventory:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_v0`;
- explorer run:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_explorer_v0`;
- title parties:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_results_v0`.
