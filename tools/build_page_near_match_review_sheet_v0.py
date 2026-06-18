#!/usr/bin/env python3
"""Build a human-readable review sheet for the first near-match calibration batch."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from text_features import normalize_text


DEFAULT_QUEUE = Path(
    r"E:\output\DocSpectrum\page_near_match_triage_v0\page_near_match_triage_queue_v0.csv"
)
DEFAULT_EXPORT_ROOT = Path(
    r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view"
)
DEFAULT_OUTPUT = Path(
    r"E:\commons\DocSpectrum\page_near_match_first30_review_v0.csv"
)
REVIEW_FIELDS = [
    "review_label",
    "review_confidence",
    "reviewer",
    "review_note",
    "reviewed_at",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def page_segments(
    export_root: Path,
    object_id: str,
    crc32: str,
    page_number: str,
) -> list[str]:
    path = export_root / object_id / f"doc_{crc32.lower()}" / "text_segments.csv"
    rows = [
        row
        for row in read_csv(path)
        if row.get("page_number") == str(int(float(page_number)))
    ]
    rows.sort(
        key=lambda row: (
            safe_float(row.get("y1")),
            safe_float(row.get("x1")),
            row.get("text_segment_id", ""),
        )
    )
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = (row.get("text_value") or "").strip()
        normalized = normalize_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(text)
    return result


def normalized_map(values: list[str]) -> dict[str, str]:
    return {normalize_text(value): value for value in values if normalize_text(value)}


def join_excerpt(values: list[str], limit: int = 30000) -> str:
    text = "\n".join(values)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"


def build(queue_path: Path, export_root: Path, output_path: Path, batch_size: int) -> None:
    existing = {row["candidate_id"]: row for row in read_csv(output_path)}
    source_rows = read_csv(queue_path)[:batch_size]
    output_rows: list[dict[str, Any]] = []

    for row in source_rows:
        left_values = page_segments(
            export_root,
            row["left_object_id"],
            row["left_crc32"],
            row["left_page_number"],
        )
        right_values = page_segments(
            export_root,
            row["right_object_id"],
            row["right_crc32"],
            row["right_page_number"],
        )
        left_map = normalized_map(left_values)
        right_map = normalized_map(right_values)
        shared_keys = sorted(left_map.keys() & right_map.keys())
        left_only_keys = sorted(left_map.keys() - right_map.keys())
        right_only_keys = sorted(right_map.keys() - left_map.keys())
        previous = existing.get(row["candidate_id"], {})

        output_rows.append(
            {
                "review_rank": row["review_rank"],
                "review_label": previous.get("review_label", row.get("review_label", "")),
                "review_confidence": previous.get(
                    "review_confidence",
                    row.get("review_confidence", ""),
                ),
                "reviewer": previous.get("reviewer", row.get("reviewer", "")),
                "review_note": previous.get("review_note", row.get("review_note", "")),
                "reviewed_at": previous.get("reviewed_at", row.get("reviewed_at", "")),
                "candidate_id": row["candidate_id"],
                "candidate_strength": row["candidate_strength"],
                "left_object": row["left_object_id"],
                "left_organization": row["left_cohort"],
                "left_file": row["left_file_name"],
                "left_page": row["left_page_number"],
                "left_pdf_path": row["left_pdf_path"],
                "right_object": row["right_object_id"],
                "right_organization": row["right_cohort"],
                "right_file": row["right_file_name"],
                "right_page": row["right_page_number"],
                "right_pdf_path": row["right_pdf_path"],
                "section": row["left_section_code"],
                "structural_similarity": row["near_match_similarity_v0"],
                "text_jaccard": row["text_segment_jaccard"],
                "shared_text_segments_metric": row["shared_text_segment_count"],
                "rare_shared_text_segments": row["rare_shared_text_segment_count"],
                "shared_table_layouts": row["shared_table_layout_count"],
                "shared_table_content": row["shared_table_content_count"],
                "shared_text_excerpt": join_excerpt(
                    [left_map[key] for key in shared_keys]
                ),
                "left_only_text_excerpt": join_excerpt(
                    [left_map[key] for key in left_only_keys]
                ),
                "right_only_text_excerpt": join_excerpt(
                    [right_map[key] for key in right_only_keys]
                ),
                "left_page_text": join_excerpt(left_values),
                "right_page_text": join_excerpt(right_values),
                "review_instruction": (
                    "Compare both PDF pages and text evidence; fill only "
                    "review_label, review_confidence, reviewer, review_note, reviewed_at."
                ),
            }
        )

    fields = list(output_rows[0]) if output_rows else []
    write_csv(output_path, output_rows, fields)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a human-readable first-batch near-match review sheet."
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=30)
    args = parser.parse_args()
    build(args.queue, args.export_root, args.output, args.batch_size)
    print(args.output)


if __name__ == "__main__":
    main()
