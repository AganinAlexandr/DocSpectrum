#!/usr/bin/env python3
"""Build a stable human-review queue for page near-match candidates."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = Path(
    r"E:\output\DocSpectrum\page_near_match_v0\page_near_match_review_candidates_v0.csv"
)
DEFAULT_DOCUMENTS = Path(
    r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34\documents_index.csv"
)
DEFAULT_EXPORT_ROOT = Path(
    r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\page_near_match_triage_v0")
DEFAULT_LABELS = Path(
    r"E:\commons\DocSpectrum\page_near_match_triage_labels_v0.csv"
)

LABEL_FIELDS = [
    "candidate_id",
    "review_label",
    "review_confidence",
    "reviewer",
    "review_note",
    "reviewed_at",
]
LABEL_VALUES = {
    "borrowing_candidate": (
        "Substantial non-normative content or layout reuse; requires follow-up, "
        "not a legal conclusion."
    ),
    "normative_form": (
        "Similarity is primarily explained by a standard, regulatory or common "
        "industry form."
    ),
    "estimate_boilerplate": (
        "Similarity is primarily explained by recurring estimate wording or "
        "estimate-system output."
    ),
    "shared_technical_content": (
        "Documents independently express the same technical solution or data "
        "without enough evidence of direct reuse."
    ),
    "false_positive": (
        "Near-match evidence is not materially similar under expert review."
    ),
    "uncertain": "Evidence is insufficient or mixed; retain for later review.",
}
CONFIDENCE_VALUES = {"high", "medium", "low"}


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


def safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def load_documents(
    documents_path: Path,
    export_root: Path,
    candidates: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    cohort_by_crc: dict[str, str] = {}
    for row in candidates:
        cohort_by_crc[row["query_bundle_id"].removeprefix("doc_").lower()] = row["query_cohort"]
        cohort_by_crc[row["neighbor_bundle_id"].removeprefix("doc_").lower()] = row[
            "neighbor_cohort"
        ]

    documents: dict[str, dict[str, str]] = {}
    for row in read_csv(documents_path):
        crc32 = row["crc32"].lower()
        document_csv = export_root / row["object_id"] / row["bundle_id"] / "documents.csv"
        export_row = read_csv(document_csv)[0] if document_csv.exists() else {}
        documents[crc32] = {
            "object_id": row["object_id"],
            "bundle_id": row["bundle_id"],
            "section_code": row["section_code"],
            "cohort": cohort_by_crc.get(crc32, "UNKNOWN"),
            "file_name": row["file_name"],
            "page_count": row["page_count"],
            "pdf_path": export_row.get("file_path", ""),
            "parse_status": export_row.get("parse_status", ""),
        }
    return documents


def load_labels(path: Path) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        candidate_id = row.get("candidate_id", "")
        if not candidate_id:
            continue
        label = row.get("review_label", "")
        confidence = row.get("review_confidence", "")
        if label and label not in LABEL_VALUES:
            raise ValueError(f"Unknown review_label for {candidate_id}: {label}")
        if confidence and confidence not in CONFIDENCE_VALUES:
            raise ValueError(
                f"Unknown review_confidence for {candidate_id}: {confidence}"
            )
        labels[candidate_id] = {field: row.get(field, "") for field in LABEL_FIELDS}
    return labels


def review_priority(row: dict[str, str]) -> tuple[int, float, float, str]:
    strength_rank = 0 if row["candidate_strength"] == "rare_text_high_overlap" else 1
    return (
        strength_rank,
        -safe_float(row["text_segment_jaccard"]),
        -safe_float(row["near_match_similarity_v0"]),
        row["candidate_id"],
    )


def side_fields(prefix: str, crc32: str, page: str, document: dict[str, str]) -> dict[str, Any]:
    return {
        f"{prefix}_crc32": crc32,
        f"{prefix}_object_id": document.get("object_id", ""),
        f"{prefix}_cohort": document.get("cohort", ""),
        f"{prefix}_section_code": document.get("section_code", ""),
        f"{prefix}_file_name": document.get("file_name", ""),
        f"{prefix}_pdf_path": document.get("pdf_path", ""),
        f"{prefix}_page_number": safe_int(page),
        f"{prefix}_page_count": safe_int(document.get("page_count")),
        f"{prefix}_parse_status": document.get("parse_status", ""),
    }


def build(
    candidates_path: Path,
    documents_path: Path,
    export_root: Path,
    output_dir: Path,
    labels_path: Path,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    candidates = read_csv(candidates_path)
    candidates.sort(key=review_priority)
    documents = load_documents(documents_path, export_root, candidates)
    existing_labels = load_labels(labels_path)

    label_rows: list[dict[str, str]] = []
    queue_rows: list[dict[str, Any]] = []
    missing_documents: set[str] = set()
    for rank, candidate in enumerate(candidates, start=1):
        candidate_id = candidate["candidate_id"]
        labels = existing_labels.get(
            candidate_id,
            {field: "" for field in LABEL_FIELDS},
        )
        labels["candidate_id"] = candidate_id
        label_rows.append(labels)

        left_crc = candidate["left_crc32"].lower()
        right_crc = candidate["right_crc32"].lower()
        left_document = documents.get(left_crc, {})
        right_document = documents.get(right_crc, {})
        if not left_document:
            missing_documents.add(left_crc)
        if not right_document:
            missing_documents.add(right_crc)

        queue_rows.append(
            {
                "review_rank": rank,
                "review_status": "reviewed" if labels.get("review_label") else "pending",
                **labels,
                "candidate_strength": candidate["candidate_strength"],
                "section_relation": candidate["section_relation"],
                "near_match_similarity_v0": candidate["near_match_similarity_v0"],
                "text_segment_jaccard": candidate["text_segment_jaccard"],
                "shared_text_segment_count": candidate["shared_text_segment_count"],
                "rare_shared_text_segment_count": candidate[
                    "rare_shared_text_segment_count"
                ],
                "shared_text_global_idf_sum": candidate["shared_text_global_idf_sum"],
                "max_shared_text_global_idf": candidate["max_shared_text_global_idf"],
                "table_layout_jaccard": candidate["table_layout_jaccard"],
                "shared_table_layout_count": candidate["shared_table_layout_count"],
                "table_content_jaccard": candidate["table_content_jaccard"],
                "shared_table_content_count": candidate["shared_table_content_count"],
                **side_fields(
                    "left",
                    left_crc,
                    candidate["left_page_number"],
                    left_document,
                ),
                **side_fields(
                    "right",
                    right_crc,
                    candidate["right_page_number"],
                    right_document,
                ),
                "interpretation_note": candidate["interpretation_note"],
            }
        )

    if missing_documents:
        raise ValueError(f"Missing document metadata for CRC32: {sorted(missing_documents)}")

    labels_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(labels_path, label_rows, LABEL_FIELDS)

    queue_fields = list(queue_rows[0]) if queue_rows else []
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "page_near_match_triage_queue_v0.csv", queue_rows, queue_fields)
    write_csv(
        output_dir / "page_near_match_triage_label_dictionary_v0.csv",
        [
            {"field": "review_label", "value": value, "description": description}
            for value, description in LABEL_VALUES.items()
        ]
        + [
            {
                "field": "review_confidence",
                "value": value,
                "description": "Expert confidence in the selected review label.",
            }
            for value in ("high", "medium", "low")
        ],
        ["field", "value", "description"],
    )

    label_counts = Counter(
        row["review_label"] or "pending" for row in label_rows
    )
    summary = {
        "schema_version": "page_near_match_triage_v0",
        "generated_at": generated_at,
        "candidate_count": len(queue_rows),
        "labels_path": str(labels_path),
        "label_counts": dict(sorted(label_counts.items())),
        "candidate_strength_counts": dict(
            sorted(Counter(row["candidate_strength"] for row in queue_rows).items())
        ),
        "section_counts": dict(
            sorted(
                Counter(
                    f"{row['left_section_code']}|{row['right_section_code']}"
                    for row in queue_rows
                ).items()
            )
        ),
        "pdf_path_coverage": sum(
            bool(row["left_pdf_path"] and row["right_pdf_path"]) for row in queue_rows
        ),
        "rules": [
            "labels are human ground-truth inputs and are never inferred by the generator.",
            "existing labels are preserved by candidate_id on rebuild.",
            "title-page near-matches are excluded; this queue contains the body review shortlist only.",
            "borrowing_candidate is a research label, not a legal conclusion.",
        ],
    }
    (output_dir / "page_near_match_triage_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a stable human-review queue for page near-match v0."
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    args = parser.parse_args()
    summary = build(
        args.candidates,
        args.documents,
        args.export_root,
        args.output_dir,
        args.labels,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
