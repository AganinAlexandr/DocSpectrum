# text axis v0.2

`comparison_results_v0_2` is the first first-order text-axis checkpoint.

Generated artifacts:

- `E:/output/DocSpectrum/comparison_results_v0_2_18_n2`

Input corpus:

- `E:/output/DocSpectrum/element_base_v0_18_n2`
- `E:/output/DocSpectrum/export`
- `1190` same-section pairs

## Policy

The text axis is a scoring axis, not a QC/domain feature.

Current scoring fields:

- `combined_similarity_v0_2`
- `signature_similarity_v0_1`
- `text_similarity_v0_2`

`feature_cosine_v0` remains diagnostic only.

Combined score:

- structural signatures: weight `0.50`
- text axis: weight `0.50`

Text subaxes:

- `text_segment_hash_jaccard`, weight `0.35`
- `text_word_shingle_jaccard`, weight `0.65`

Privacy rule:

- generated artifacts store text hashes and counts only;
- raw text is not written to comparison JSON/CSV.

## Expanded Corpus Run

`comparison_results_v0_2_18_n2` contains `1190` rows.

Combined similarity by section:

| Section | Pairs | Min | Median | Max |
|---|---:|---:|---:|---:|
| АР | 153 | 0.4153 | 0.5728 | 0.8384 |
| КР | 153 | 0.4047 | 0.6034 | 0.8587 |
| ИД | 153 | 0.7900 | 0.8951 | 0.9563 |
| ИОС5.1 | 153 | 0.3713 | 0.4696 | 0.7088 |
| ИОС5.4.1 | 153 | 0.1172 | 0.3446 | 0.7263 |
| ИОС5.5.1 | 153 | 0.2805 | 0.4636 | 0.6863 |
| ПОКР | 136 | 0.3351 | 0.5327 | 0.7856 |
| СМ | 136 | 0.0779 | 0.1554 | 0.5152 |

Text similarity by section:

| Section | Pairs | Min | Median | Max |
|---|---:|---:|---:|---:|
| АР | 153 | 0.6806 | 0.8078 | 0.9545 |
| КР | 153 | 0.6427 | 0.8319 | 0.9782 |
| ИД | 153 | 0.8614 | 0.9309 | 0.9865 |
| ИОС5.1 | 153 | 0.6448 | 0.7731 | 0.9492 |
| ИОС5.4.1 | 153 | 0.1922 | 0.4783 | 0.8914 |
| ИОС5.5.1 | 153 | 0.5234 | 0.7366 | 0.9253 |
| ПОКР | 136 | 0.5434 | 0.7575 | 0.9423 |
| СМ | 136 | 0.1004 | 0.2159 | 0.6348 |

## Observations

The text axis is much less strict than exact structural signatures. This is expected: repeated formulations and stable phrase templates survive layout differences.

The control contrast remains visible:

- `ИД` median combined similarity: `0.8951`
- `СМ` median combined similarity: `0.1554`

Same-address pairs show the intended behavior: text increases similarity in ordinary design sections, while `СМ` remains comparatively low.

This is still a lexical/phrase baseline. It does not yet include:

- embeddings;
- LLM semantic judgment;
- synonym/meaning normalization;
- expert-calibrated weights.

The next text iteration should decide whether to add semantic embeddings, section-specific weights, or a domain-independent text-shingle refinement first.
