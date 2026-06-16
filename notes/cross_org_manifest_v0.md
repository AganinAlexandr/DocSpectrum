# cross-org manifest v0

`cross_org_manifest_v0` is the first inventory layer for extending DocSpectrum
from the RSPK-only UUiR corpus to other designers.

Generated artifacts:

- `E:/output/DocSpectrum/cross_org_manifest_v0/cross_org_manifest_v0.csv`
- `E:/output/DocSpectrum/cross_org_manifest_v0/cross_org_designer_summary_v0.csv`
- `E:/output/DocSpectrum/cross_org_manifest_v0/cross_org_address_groups_v0.csv`
- `E:/output/DocSpectrum/cross_org_manifest_v0/cross_org_manifest_v0.json`

Input:

- `E:/commons/DocSpectrum/Капремонт_Объекты.xlsx`

## Domain Boundary

`УУиР` and `Узел учета` are different capital-repair work types.

The v0 UUiR manifest therefore includes:

- rows with `группа = УУиР`;
- rows with `подГруппа = УУиР`.

It excludes:

- rows with `группа = Узел учета`, unless they are explicitly marked as UUiR
  by another field in a future source.

## Current Inventory

Rows:

- total UUiR rows: `236`
- RSPK baseline rows: `183`
- cross-org candidate rows: `53`

Designers:

| Designer | Rows | Source Dirs | Role |
|---|---:|---:|---|
| РСПК | 183 | 128 | baseline |
| НК-Инжениринг | 34 | 34 | main cross-org candidate |
| Сфера | 12 | 0 | registry-only until source dirs are found |
| Гамма | 3 | 3 | contrast sample |
| ГК МОС | 2 | 2 | contrast sample |
| ООО Альта | 1 | 1 | contrast sample |
| СУ ЛРМиД | 1 | 1 | contrast sample |

## Interpretation

The strongest immediate next corpus is `НК-Инжениринг`:

- enough rows for a first cross-org run;
- all source directories are currently found in `E:/MSE_арх`;
- most objects are combined `ОВ, ГВС`, which differs from the RSPK split
  `ОВ`/`ГВС` pattern and is useful for stress-testing the section logic.

`Сфера` is potentially valuable but currently needs source-folder resolution:

- 12 registry rows;
- 0 source directories found by the current `object_id` prefix rule.

The small designers are useful as contrast samples, not standalone statistics.

## Next Step

Before running explorer exports, pick one of two modes:

- `NK-first`: process `НК-Инжениринг` only, then compare against the RSPK baseline.
- `available-cross-org`: process all non-RSPK rows with found source directories
  (`41` rows), treating small designers as contrast only.

Axis C should remain clearly separated from Axis A/B:

- Axis A/B can test transfer of content/system and size/TEI patterns.
- Axis C tests organization/handwriting: within-designer distances should be
  lower than cross-designer distances if the electronic footprint is stable.
