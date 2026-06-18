#!/usr/bin/env python3
"""Summarize the first completed human calibration batch for page near-match."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_QUEUE = Path(
    r"E:\output\DocSpectrum\page_near_match_triage_v0\page_near_match_triage_queue_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\page_near_match_calibration_v0"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def floats(rows: list[dict[str, str]], field: str) -> list[float]:
    return [float(row[field]) for row in rows]


def round4(value: float) -> float:
    return round(value, 4)


def build(queue_path: Path, output_dir: Path, batch_size: int) -> dict[str, Any]:
    rows = read_csv(queue_path)[:batch_size]
    if len(rows) != batch_size:
        raise ValueError(f"Expected {batch_size} calibration rows, got {len(rows)}")
    pending = [row["candidate_id"] for row in rows if not row.get("review_label")]
    if pending:
        raise ValueError(f"Calibration batch still has pending labels: {pending}")

    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_label[row["review_label"]].append(row)

    summary_rows: list[dict[str, Any]] = []
    for label, group in sorted(by_label.items()):
        structure = floats(group, "near_match_similarity_v0")
        text = floats(group, "text_segment_jaccard")
        rare = floats(group, "rare_shared_text_segment_count")
        layouts = floats(group, "shared_table_layout_count")
        summary_rows.append(
            {
                "review_label": label,
                "candidate_count": len(group),
                "section_counts": "|".join(
                    f"{key}:{value}"
                    for key, value in sorted(
                        Counter(row["left_section_code"] for row in group).items()
                    )
                ),
                "structural_similarity_min": round4(min(structure)),
                "structural_similarity_median": round4(median(structure)),
                "structural_similarity_max": round4(max(structure)),
                "text_jaccard_min": round4(min(text)),
                "text_jaccard_median": round4(median(text)),
                "text_jaccard_max": round4(max(text)),
                "rare_shared_text_min": int(min(rare)),
                "rare_shared_text_median": round4(median(rare)),
                "rare_shared_text_max": int(max(rare)),
                "shared_table_layout_median": round4(median(layouts)),
            }
        )

    detail_fields = [
        "review_rank",
        "candidate_id",
        "review_label",
        "review_confidence",
        "left_object_id",
        "left_cohort",
        "left_section_code",
        "left_file_name",
        "left_page_number",
        "right_object_id",
        "right_cohort",
        "right_section_code",
        "right_file_name",
        "right_page_number",
        "near_match_similarity_v0",
        "text_segment_jaccard",
        "shared_text_segment_count",
        "rare_shared_text_segment_count",
        "shared_table_layout_count",
        "shared_table_content_count",
        "review_note",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "page_near_match_calibration_summary_v0.csv",
        summary_rows,
        list(summary_rows[0]),
    )
    write_csv(
        output_dir / "page_near_match_calibration_cases_v0.csv",
        rows,
        detail_fields,
    )

    label_counts = Counter(row["review_label"] for row in rows)
    result = {
        "schema_version": "page_near_match_calibration_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "batch_size": batch_size,
        "completed_count": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "borrowing_candidate_count": label_counts.get("borrowing_candidate", 0),
        "negative_for_borrowing_count": (
            len(rows) - label_counts.get("borrowing_candidate", 0)
        ),
        "interpretation": [
            "all first-batch candidates are strong cross-organization near-matches.",
            "none was labeled borrowing_candidate by the domain expert.",
            "high structural/text overlap alone is insufficient evidence of borrowing.",
            "the dominant explanations are manufacturer forms, estimate-system boilerplate, and shared technical material.",
            "the batch is a negative-control calibration set for UC3, not a positive borrowing eval set.",
        ],
        "files": {
            "summary": "page_near_match_calibration_summary_v0.csv",
            "cases": "page_near_match_calibration_cases_v0.csv",
        },
    }
    (output_dir / "page_near_match_calibration_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize completed page near-match calibration labels."
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.queue, args.output_dir, args.batch_size),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
