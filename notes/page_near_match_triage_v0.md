# Page near-match triage v0

## Purpose

RP-022 established that the page near-match layer preserves exact recall and
produces a useful body-page shortlist. Before those candidates can influence
the typical-element library or UC3, the shortlist needs human ground truth.

The triage layer separates:

- `borrowing_candidate`;
- `normative_form`;
- `estimate_boilerplate`;
- `shared_technical_content`;
- `false_positive`;
- `uncertain`.

`borrowing_candidate` is a research routing label, not a legal conclusion.

## Stable Human Input

The canonical editable file is:

`E:/commons/DocSpectrum/page_near_match_triage_labels_v0.csv`

It contains only:

- `candidate_id`;
- `review_label`;
- `review_confidence`;
- `reviewer`;
- `review_note`;
- `reviewed_at`.

The generator preserves existing values by `candidate_id` and adds new
candidates with empty labels. Generated output never becomes the source of
truth for human decisions.

## Review Queue

The joined queue is generated at:

`E:/output/DocSpectrum/page_near_match_triage_v0/page_near_match_triage_queue_v0.csv`

Each row contains:

- both source PDF paths and page numbers;
- object, cohort, section and file metadata;
- structural near-match score;
- rare shared text evidence;
- table layout/content overlap;
- editable review fields joined from the canonical labels file.

The queue includes only the `240` body review candidates from RP-022. The `367`
title-page near-matches are deliberately excluded because title similarity is
primarily a normative-form signal, not a borrowing signal.

Priority order:

1. `rare_text_high_overlap`;
2. higher text-segment Jaccard;
3. higher structural near-match similarity.

## Excel / Power Query

`analytics/pq/PageNearMatchTriage_v0.pq` loads the joined queue into Excel.
Filters should normally start with:

- `review_status = pending`;
- `candidate_strength`;
- `left_section_code`;
- `review_label`.

Human decisions should be written to the canonical labels CSV, not to a
refreshable Power Query result table.

## Outputs

- `page_near_match_triage_queue_v0.csv`;
- `page_near_match_triage_label_dictionary_v0.csv`;
- `page_near_match_triage_v0.json`.

## Ground-Truth Rule

Near-match weights and thresholds must not be changed from impressions gathered
outside this explicit label set. Once a meaningful portion is reviewed, labels
can be split into calibration and held-out evaluation subsets before UC3
threshold tuning.
