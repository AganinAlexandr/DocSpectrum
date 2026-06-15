# pairwise DF/IDF v0.3

`comparison_results_v0_3` is the first pairwise integration of the corpus-frequency entity library.

Generated artifacts:

- `E:/output/DocSpectrum/comparison_results_v0_3_18_n2`

Inputs:

- `E:/output/DocSpectrum/element_base_v0_18_n2`
- `E:/output/DocSpectrum/export`
- `E:/output/DocSpectrum/corpus_frequency_v0_18_n2`
- `E:/output/DocSpectrum/comparison_results_v0_2_18_n2/comparison_results_v0_2.csv`

## Purpose

This layer compares same-section pairs through IDF-weighted entity overlap.

It is additive:

- `idf_similarity_v0_3` is the new scoring field;
- `combined_similarity_v0_2` is carried as a baseline reference;
- `page_signature_idf_jaccard` is diagnostic only until near-match/bucketed page signatures are available.

## Scoring Entity Weights

Pre-eval placeholder weights:

- `text_segment`: `0.25`
- `text_word_shingle`: `0.35`
- `table_cell_text`: `0.15`
- `table_layout_signature`: `0.15`
- `table_content_signature`: `0.10`

`page_signature` is excluded from scoring because exact page hashes are strictness-prone and currently overstate originality.

## Privacy

Artifacts store hashes and counts only. Raw text is not written.

## Expanded Corpus Run

Corpus:

- pairs: `1190`
- scoring axis status: `5950 measured`

Median `idf_similarity_v0_3` by section:

| Section | idf v0.3 | combined v0.2 | text v0.2 | page diagnostic |
|---|---:|---:|---:|---:|
| АР | 0.6331 | 0.5728 | 0.8078 | 0.0000 |
| ИД | 0.9282 | 0.8951 | 0.9309 | 0.4162 |
| ИОС5.1 | 0.5961 | 0.4696 | 0.7731 | 0.0492 |
| ИОС5.4.1 | 0.3284 | 0.3446 | 0.4783 | 0.0685 |
| ИОС5.5.1 | 0.5953 | 0.4640 | 0.7366 | 0.0501 |
| КР | 0.6859 | 0.6034 | 0.8319 | 0.0535 |
| ПОКР | 0.5947 | 0.5327 | 0.7575 | 0.0720 |
| СМ | 0.1545 | 0.1554 | 0.2159 | 0.0096 |

Subaxis distribution across all pairs:

| Axis | p10 | median | p90 |
|---|---:|---:|---:|
| `text_segment_idf_jaccard` | 0.2212 | 0.6700 | 0.8936 |
| `text_word_shingle_idf_jaccard` | 0.3755 | 0.7540 | 0.8903 |
| `table_cell_text_idf_jaccard` | 0.1566 | 0.7415 | 1.0000 |
| `table_layout_signature_idf_jaccard` | 0.0431 | 0.2177 | 1.0000 |
| `table_content_signature_idf_jaccard` | 0.0532 | 0.1776 | 0.9278 |
| `page_signature_idf_jaccard` | 0.0000 | 0.0555 | 0.3802 |

First interpretation:

- `page_signature` stays diagnostic: its low median confirms exact page hashes are too strict for scoring.
- IDF weighting reduces the text-only floor, but does not eliminate template similarity in highly standardized sections.
- `ИД` remains very high, which matches its strongly templated nature.
- `СМ` stays low and remains a useful control section.

## Limits

This layer does not yet include:

- eval-calibrated weights;
- near-match/bucketed page signatures;
- embeddings or LLM semantic similarity;
- image/vector graphical signatures.
