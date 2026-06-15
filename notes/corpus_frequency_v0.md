# corpus frequency v0

`corpus_frequency_v0` is the first section-to-library layer for typicality/originality analysis.

Generated artifacts:

- `E:/output/DocSpectrum/corpus_frequency_v0_18_n2`

Inputs:

- `E:/output/DocSpectrum/element_base_v0_18_n2`
- `E:/output/DocSpectrum/export`

## Purpose

This layer is not pairwise comparison. It builds a reusable corpus index, then scores each section against the library.

Two library structures are separated:

- section library: whole-section rows from `documents_index.csv`;
- extracted entity library: inverted index of hash-only text, structural, and table-cell entities with DF/IDF.

The extracted entity library currently contains:

- `text_segment`
- `text_word_shingle`
- `page_signature`
- `table_layout_signature`
- `table_content_signature`
- `table_cell_text`

Raw text is not written to artifacts.

## Buckets

Frequency buckets use same-section document frequency:

- `typical`: entity appears in at least `50%` of documents with the same `section_code`;
- `shared_rare`: entity appears in more than one same-section document but below the typical threshold;
- `original`: entity appears in one same-section document;
- `low_population`: section has fewer than two documents.

`shared_rare` rows include `section_documents` and `section_objects`, which makes them a first bridge toward future `fragment_matches` / `source_matches`.

## Expanded Corpus Run

Corpus:

- documents: `143`
- sections: `9`
- entity rows: `49000`
- `page_signature`: `1942`
- `table_cell_text`: `5093`
- `table_content_signature`: `906`
- `table_layout_signature`: `888`
- `text_segment`: `30240`
- `text_word_shingle`: `9931`

Frequency buckets:

- `typical`: `12883`
- `shared_rare`: `11920`
- `original`: `22464`
- `low_population`: `1733`

Median shares by entity kind:

| Entity kind | typical | original |
|---|---:|---:|
| `page_signature` | 0.2000 | 0.5429 |
| `table_cell_text` | 0.9534 | 0.0038 |
| `table_content_signature` | 0.5000 | 0.2000 |
| `table_layout_signature` | 0.6000 | 0.2000 |
| `text_segment` | 0.9301 | 0.0170 |
| `text_word_shingle` | 0.9537 | 0.0089 |

Median shares by section for `text_word_shingle`:

| Section | typical | original |
|---|---:|---:|
| АР | 0.9446 | 0.0278 |
| КР | 0.9627 | 0.0164 |
| ИД | 0.9664 | 0.0057 |
| ИОС5.1 | 0.9683 | 0.0050 |
| ИОС5.4.1 | 0.8674 | 0.0072 |
| ИОС5.5.1 | 0.9591 | 0.0034 |
| ПОКР | 0.9643 | 0.0028 |
| СМ | 0.6860 | 0.0190 |

Notable first signals:

- `ИД` is almost entirely typical, as expected for a highly templated section.
- `СМ` has lower typicality and more rare/original material than most sections.
- `ИОС5.4.1` contains the most visible originality spikes among engineering sections in this run.
- `table_cell_text` behaves like a strong template layer: median typical share is `0.9534`.
- `page_signature` is much more variable: median original share is `0.5429`, which makes page composition a useful counterweight to boilerplate text.
- Table layout/content signatures sit between text boilerplate and page composition, with median typical shares `0.6000` and `0.5000`.

## Limits

The `50%` typicality threshold is accepted for experiment, not final calibration.

This layer does not yet include:

- entity-level source ranking;
- table-cell shingles;
- image/vector graphical signatures beyond page/table aggregates;
- eval-calibrated thresholds;
- semantic embeddings.
