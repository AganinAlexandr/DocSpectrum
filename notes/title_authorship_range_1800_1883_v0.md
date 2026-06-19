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
- selected PDFs: 84;
- unique CRC32 values: 84;
- selected sections: 79 `KR`, 5 `POKR`;
- explorer failures: 0;
- title parties: 85 across 84 documents;
- two-title documents: 83;
- four-title documents: 1.

## Subcontractor case

Object `1869_25` contains four title pages. Pages 3-4 identify the effective
subcontractor:

- organization: `Spektr`;
- GIP: `Egupov V. V`.

## Incremental addition

Objects `1830_25` and `1846_25` became available after the first range run and
were added without rerunning Explorer for the other objects:

- `1830_25`: `KR`, organization `OOO VITMAR`, GIP `Savchenkov V.M.`;
- `1846_25`: `POKR`, organization `Stroy Montazh SP`, GIP `Loktev A.N.`.

## Outputs

- selection and inventory:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_v0`;
- explorer run:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_explorer_v0`;
- title parties:
  `E:/output/DocSpectrum/title_authorship_range_1800_1883_results_v0`.
