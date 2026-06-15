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
- extracted entity library: inverted index of hash-only text entities with DF/IDF.

The extracted entity library currently contains:

- `text_segment`
- `text_word_shingle`

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
- entity rows: `40171`
- `text_segment`: `30240`
- `text_word_shingle`: `9931`

Frequency buckets:

- `typical`: `10997`
- `shared_rare`: `10709`
- `original`: `16924`
- `low_population`: `1541`

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

## Limits

The `50%` typicality threshold is accepted for experiment, not final calibration.

This layer does not yet include:

- structural signatures in the entity library;
- table-cell entities;
- entity-level source ranking;
- eval-calibrated thresholds;
- semantic embeddings.
