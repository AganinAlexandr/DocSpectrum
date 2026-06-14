# object_registry_v0

`object_registry_v0` is the first domain registry for the Podolsk UUiR validation corpus.

It joins three layers:

- source object list from `E:/commons/DocSpectrum/Капремонт_дома_УУиР_Подольск.xlsx`;
- source PD folder under `E:/MSE_арх`;
- TEI indicators from the explanatory note XML, including OKEI unit decoding from `explanatorynote-01-06.xsd`.

Generated artifacts are stored outside git:

- `E:/output/DocSpectrum/object_registry_v0/object_registry_v0.csv`
- `E:/output/DocSpectrum/object_registry_v0/object_tei_overview_v0.csv`
- `E:/output/DocSpectrum/object_registry_v0/address_tei_consistency_v0.csv`
- `E:/output/DocSpectrum/object_registry_v0/object_tei_long_v0.csv`
- `E:/output/DocSpectrum/object_registry_v0/object_registry_v0.jsonl`
- `E:/output/DocSpectrum/object_registry_v0/summary.json`

Current run:

- objects in Excel: `35`
- source folders found: `35`
- explanatory note XML files found: `34`
- objects with TEI: `34`
- object without required explanatory note XML: `1683_25`
- subgroups: `ГВС` = `15`, `ОВ` = `20`
- same-address groups: `5`
- same-address inconsistent groups: `1`

Same-address TEI consistency is a quality-control layer for source PD. In the current pre-expertise corpus, `Подольск, мкр. Климовск, ул. Симферопольская, 13` has inconsistent TEI values between `1680_25` and `1684_25`. Per human domain input, TEI values for one address should be identical, so this is treated as a designer/source-PD error, not as a legitimate house difference.

The registry is intentionally separate from `section_passport`: it describes the object and its source folder, while the passport remains specific to a particular parsed section.

TEI values are useful as an independent domain similarity layer. For example, number of entrances, number of floors, building dimensions, footprint area, building volume, and total area can be used to create an architectural-nearness vector before comparing PDF element spectra.

Power Query entry points:

- `analytics/pq/ObjectRegistry_v0.pq`
- `analytics/pq/ObjectTeiLong_v0.pq`
- `analytics/pq/ObjectTeiConsistency_v0.pq`
