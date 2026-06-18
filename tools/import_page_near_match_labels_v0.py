#!/usr/bin/env python3
"""Merge a human-exported near-match label CSV into the canonical label store."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_page_near_match_triage_v0 import (
    CONFIDENCE_VALUES,
    LABEL_FIELDS,
    LABEL_VALUES,
)


DEFAULT_INPUT = Path(
    r"C:\Users\alexa\Downloads\page_near_match_triage_labels_v0.csv"
)
DEFAULT_CANONICAL = Path(
    r"E:\commons\DocSpectrum\page_near_match_triage_labels_v0.csv"
)
DEFAULT_SUMMARY = Path(
    r"E:\output\DocSpectrum\page_near_match_triage_v0\label_import_v0.json"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate(rows: list[dict[str, str]], source: str) -> None:
    ids = [row.get("candidate_id", "") for row in rows]
    if any(not candidate_id for candidate_id in ids):
        raise ValueError(f"{source}: candidate_id is required")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{source}: duplicate candidate_id")
    for row in rows:
        label = row.get("review_label", "")
        confidence = row.get("review_confidence", "")
        if label and label not in LABEL_VALUES:
            raise ValueError(f"{source}: unknown review_label {label}")
        if confidence and confidence not in CONFIDENCE_VALUES:
            raise ValueError(f"{source}: unknown review_confidence {confidence}")


def merge(input_path: Path, canonical_path: Path, summary_path: Path) -> dict[str, Any]:
    incoming = read_csv(input_path)
    canonical = read_csv(canonical_path)
    validate(incoming, "input")
    validate(canonical, "canonical")

    canonical_ids = {row["candidate_id"] for row in canonical}
    unknown_ids = sorted(
        row["candidate_id"] for row in incoming if row["candidate_id"] not in canonical_ids
    )
    if unknown_ids:
        raise ValueError(f"Input contains unknown candidate ids: {unknown_ids}")

    incoming_by_id = {row["candidate_id"]: row for row in incoming}
    imported_rows = 0
    imported_labeled = 0
    pending_with_note: list[str] = []
    for row in canonical:
        candidate_id = row["candidate_id"]
        incoming_row = incoming_by_id.get(candidate_id)
        if incoming_row is None:
            continue
        for field in LABEL_FIELDS[1:]:
            row[field] = incoming_row.get(field, "")
        imported_rows += 1
        if incoming_row.get("review_label"):
            imported_labeled += 1
        elif incoming_row.get("review_note"):
            pending_with_note.append(candidate_id)

    write_csv(canonical_path, canonical)
    summary = {
        "schema_version": "page_near_match_label_import_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_path": str(input_path),
        "canonical_path": str(canonical_path),
        "input_row_count": len(incoming),
        "imported_row_count": imported_rows,
        "imported_labeled_count": imported_labeled,
        "pending_with_note_count": len(pending_with_note),
        "pending_with_note_candidate_ids": pending_with_note,
        "canonical_labeled_count": sum(bool(row.get("review_label")) for row in canonical),
        "canonical_pending_count": sum(not row.get("review_label") for row in canonical),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import human near-match labels into the canonical CSV."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    print(
        json.dumps(
            merge(args.input, args.canonical, args.summary),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
