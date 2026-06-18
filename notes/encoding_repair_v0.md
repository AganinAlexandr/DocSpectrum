# Encoding repair v0

## Purpose

Some explorer text segments contain a narrow Cyrillic corruption pattern while
`encoding_status` is still `ok`. Because text hashes are built after
normalization, this created false uniqueness across corpus frequency, pairwise
text similarity, candidate libraries and coverage.

The shared Checker-to-DocSpectrum handoff identified this route as higher
priority than title-only handling because the defect affects the whole text
layer.

## Repair Map

`tools/text_features.normalize_text` now repairs:

```text
Ð / ð -> Р / р
Ö / ö -> Ц / ц
Þ / þ -> Ю / ю
```

The case pairs matter because explorer `normalized_text` can already contain
lowercased corrupted characters.

Examples:

```text
ПÐОЕКТНАЯ ДОКУМЕНТАЦИЯ -> ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ
реконструкöиþ          -> реконструкцию
документаöии           -> документации
```

## Corpus Reach

Exact Unicode inspection of the combined RSPK35 + NK34 exports found:

```text
Ð: 126 lines / 6 files
ö: 103 lines / 7 files
þ: 3065 lines / 43 files
```

The larger `þ` count is real and appears in words such as `применениþ`,
`вклþчая`, `устанавливаþщими`.

## Verification

Regression tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Result:

```text
Ran 3 tests
OK
```

Rebuilt:

- `corpus_frequency_v0_rpsk35_nk34`;
- `comparison_results_v0_2_rpsk35_nk34`;
- `comparison_results_v0_3_rpsk35_nk34`;
- `text_element_library_v0`;
- `section_library_report_v0`.

## Before / After

Corpus-frequency unique entity counts:

```text
text_segment       66602 -> 66360  (-242)
text_word_shingle  23817 -> 23312  (-505)
table_cell_text    15302 -> 15259   (-43)
```

Text candidate library:

```text
candidate_count       43740 -> 42993  (-747)
text_segment          27865 -> 27623  (-242)
text_word_shingle     15875 -> 15370  (-505)
org_text_pattern      36355 -> 35606  (-749)
cross_org_common       4139 ->  4322  (+183)
org_distinctive        3246 ->  3065  (-181)
cross_org_text_bridge   250 ->   250  (stable)
```

Interpretation:

- false exact-hash uniqueness was removed;
- some organization-specific entities correctly merged into shared/common
  entities;
- the rare cross-org review shortlist remained stable;
- section coverage medians did not shift, so the repair is not a broad scoring
  perturbation.

Pairwise IDF medians changed only in affected sections:

```text
ИОС5.1    0.1115 -> 0.1133
ИОС5.4.1  0.0573 -> 0.0598
КР        0.0750 -> 0.0807
СМ        0.1113 -> 0.1114
```

Combined report triage:

```text
review_clear 379 -> 407
review_watch  95 ->  67
review_high    0 ->   0
```

The drop in watch signals is expected: repaired text no longer looks foreign
merely because the same Cyrillic letters were encoded differently.

## Limits

- This is a deliberately narrow known-corruption map, not a general encoding
  recovery engine.
- Other broken encodings still require extraction QC or a broader repair
  strategy.
- Raw explorer exports are unchanged; repair happens in the common
  normalization layer before hashing.
