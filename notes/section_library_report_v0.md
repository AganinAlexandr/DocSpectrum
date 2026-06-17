# Section library report v0

## Purpose

This checkpoint combines the table-form library layer and the text library
layer into one section-level consumer report for HC-010 UC1:

- how much of a section is explained by the known library;
- what remains as library-unexplained residual;
- whether the matched layer conforms to the document organization;
- whether foreign-pattern or copy-review signals need attention.

It is a reporting layer over already-built artifacts. It does not change table
or text extraction logic.

## Tool

```powershell
python E:\repos\DocSpectrum\tools\build_section_library_report_v0.py `
  --table-coverage E:\output\DocSpectrum\typical_element_coverage_v0\typical_element_section_coverage_v0.csv `
  --text-coverage E:\output\DocSpectrum\text_element_library_v0\text_element_section_coverage_v0.csv `
  --output-dir E:\output\DocSpectrum\section_library_report_v0
```

Outputs:

- `section_library_report_v0.csv`;
- `section_library_report_v0.json`.

## Headline Metrics

The headline coverage metric is intentionally simple:

```text
mean(table_form_coverage_ratio, text_segment_coverage_ratio)
```

Only available measured layers are included. Text shingles are not included in
headline coverage because the shingle layer is saturated and boilerplate-prone.
The original table and text metrics stay in separate columns.

Headline fields:

- `headline_library_coverage_ratio`;
- `headline_library_residual_ratio`;
- `headline_coverage_band`;
- `headline_org_conformance_ratio`;
- `review_priority`.

The residual means:

```text
not explained by v0 table-form + exact-text-segment library
```

not:

```text
proven original authorship
```

## Run Summary

The first run on RSPK35 + NK34 produced:

```text
documents: 474
missing table coverage rows: 0
missing text coverage rows: 0
```

Review priority:

```text
review_clear 297
review_watch 148
review_high   29
```

Coverage bands:

```text
high    26
medium 331
low    117
```

Median headline coverage by cohort:

```text
NK    0.6415
RSPK  0.4569
```

This repeats the earlier pattern: NK is more template-covered than RSPK in the
current corpus.

## Section Medians

Median headline library coverage:

```text
АР        0.4905
ИД        0.6472
ИОС5.1    0.4832
ИОС5.4.1  0.5234
ИОС5.5.1  0.3356
КР        0.5376
ПОКР      0.7853
ПОС       0.4545
СМ        0.2343
```

Median headline residual:

```text
АР        0.5094
ИД        0.3528
ИОС5.1    0.5168
ИОС5.4.1  0.4766
ИОС5.5.1  0.6644
КР        0.4624
ПОКР      0.2147
ПОС       0.5455
СМ        0.7657
```

Median organization conformance is near-perfect across sections:

```text
АР        1.0000
ИД        1.0000
ИОС5.1    1.0000
ИОС5.4.1  0.9904
ИОС5.5.1  1.0000
КР        1.0000
ПОКР      1.0000
ПОС       0.9990
СМ        0.9947
```

This is still a negative-control result: the report correctly finds consistent
organization handwriting, but positive foreign-template/copy cases are needed
to validate catch ability.

## Product Reading

Safe v0 wording:

```text
The section is X% covered by known table/text library patterns.
Y% remains unexplained by the current library layers.
The matched layer is / is not consistent with the expected organization profile.
Some fragments require review because they match rare cross-organization text.
```

Unsafe v0 wording:

```text
The residual is author-created.
The review signal proves copying.
The organization author is proven.
```

## Known Limits

- The report combines only table forms and exact text-segment coverage.
- Graphics, vector forms, image candidates and near-match are not included.
- The headline metric is an unweighted v0 mean, not a calibrated product score.
- `review_priority` is triage, not a legal or authorship conclusion.
- Positive foreign-template and borrowing cases are still needed.

## Next Steps

- Add near-match for UC3 and Axis C.
- Add graphics/vector candidate layers when extraction is ready.
- Calibrate headline weighting after positive test cases.
- Export a compact Excel/PQ-friendly view for user inspection.
