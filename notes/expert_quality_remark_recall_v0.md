# Expert quality remark recall v0

This stage joins the RP-042 arena with two remark-content sources while keeping
the expert registry authoritative for review outcome.

## Authority boundary

- `clean`: first-result date equals positive-result date and answer 1 is empty;
- `remark`: dates differ or answer 1 is non-empty;
- content files never turn a registry-clean review into a remark;
- source files provide only content/count, not outcome truth.

## Two layers

- `source1_baseline`: parsed FKR archive only, retained for reference;
- `enriched`: source 1 plus unambiguous source-2 Word content.

This matters because newly recovered remarks may legitimately change enriched
count-recall. The historical zero baseline is not artificially preserved.

The productionized source-1 coverage is `115 clean / 52 remark-with-content /
32 remark-content-absent`. The exploratory probe reported `116/51/32` because
it overwrote an earlier remark row for `1284_24 POS` with a later clean row.
For first-remark analysis, preserving the earlier remark is authoritative.

## Source 2

`extract_download_remark_content_v0.py`:

- indexes `.doc/.docx` by object and KR/POS;
- prefers first-round files;
- finds the remark column by the header `Содержание замечани...`;
- handles merged Word cells through cell row/column indices;
- emits no raw remark text.

Legacy `.doc` requires Microsoft Word COM (`pywin32`).

## Quality features

Remark text is converted to:

- SHA1;
- length;
- category candidates;
- `simple_candidate`, `substantial_candidate`, or `review_needed`;
- transparent reason codes.

Depth is heuristic and must be calibrated by human review. Count-recall remains
a v0 proxy, not a complete quality metric.

`remark_recurrence_v0.csv` reports exact-text hash recurrence across documents
and roles. It is a correlation clue, not semantic equivalence.
