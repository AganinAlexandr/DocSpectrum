#!/usr/bin/env python3
"""Build a combined consumer-facing section library report v0.

This tool joins the already-built table-form and text coverage layers into one
section-level report for UC1: known-library coverage, residual, organization
conformance, foreign-pattern signals, and copy-review hooks.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TABLE_COVERAGE = Path(
    r"E:\output\DocSpectrum\typical_element_coverage_v0\typical_element_section_coverage_v0.csv"
)
DEFAULT_TEXT_COVERAGE = Path(r"E:\output\DocSpectrum\text_element_library_v0\text_element_section_coverage_v0.csv")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\section_library_report_v0")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def classify_review_priority(foreign_ratio: float, copy_review_count: int, table_borrowing_count: int) -> str:
    if table_borrowing_count > 0 or foreign_ratio >= 0.2 or copy_review_count >= 20:
        return "review_high"
    if foreign_ratio >= 0.05 or copy_review_count > 0:
        return "review_watch"
    return "review_clear"


def coverage_band(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.4:
        return "medium"
    return "low"


def build(table_coverage_path: Path, text_coverage_path: Path, output_dir: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    table_rows = read_csv(table_coverage_path)
    text_rows = read_csv(text_coverage_path)
    table_by_doc = {(row["object_id"], row["bundle_id"]): row for row in table_rows}
    text_by_doc = {(row["object_id"], row["bundle_id"]): row for row in text_rows}
    all_doc_keys = sorted(set(table_by_doc) | set(text_by_doc), key=lambda item: (table_by_doc.get(item) or text_by_doc[item])["section_code"] + item[0] + item[1])

    report_rows: list[dict[str, Any]] = []
    missing_table = 0
    missing_text = 0
    for doc_key in all_doc_keys:
        table = table_by_doc.get(doc_key)
        text = text_by_doc.get(doc_key)
        if table is None:
            missing_table += 1
        if text is None:
            missing_text += 1
        source = table or text
        assert source is not None

        table_status = table.get("coverage_status", "missing") if table else "missing"
        text_status = text.get("coverage_status", "missing") if text else "missing"
        table_coverage = safe_float(table.get("table_form_coverage_ratio") if table else "")
        table_residual = safe_float(table.get("table_form_residual_ratio") if table else "")
        table_conformance = safe_float(table.get("org_form_conformance_ratio") if table else "")
        table_foreign = safe_float(table.get("foreign_org_form_ratio") if table else "")
        table_borrowing_count = safe_int(table.get("borrowing_candidate_occurrence_count") if table else "")

        text_segment_coverage = safe_float(text.get("text_segment_coverage_ratio") if text else "")
        text_segment_residual = safe_float(text.get("text_segment_residual_ratio") if text else "")
        text_segment_conformance = safe_float(text.get("segment_org_text_conformance_ratio") if text else "")
        text_foreign = safe_float(text.get("foreign_org_text_ratio") if text else "")
        copy_review_count = safe_int(text.get("copy_review_needed_occurrence_count") if text else "")
        shingle_coverage = safe_float(text.get("text_shingle_coverage_ratio") if text else "")

        headline_coverages = []
        headline_conformances = []
        if table_status == "measured" and safe_int(table.get("total_table_count") if table else "") > 0:
            headline_coverages.append(table_coverage)
            headline_conformances.append(table_conformance)
        if text_status == "measured" and safe_int(text.get("text_segment_occurrence_count") if text else "") > 0:
            headline_coverages.append(text_segment_coverage)
            headline_conformances.append(text_segment_conformance)

        headline_coverage = average(headline_coverages)
        headline_residual = 1.0 - headline_coverage if headline_coverages else 0.0
        headline_conformance = average(headline_conformances)
        max_foreign_ratio = max(table_foreign, text_foreign)
        review_priority = classify_review_priority(max_foreign_ratio, copy_review_count, table_borrowing_count)

        report_rows.append(
            {
                "object_id": source["object_id"],
                "bundle_id": source["bundle_id"],
                "section_code": source["section_code"],
                "cohort": source.get("cohort", ""),
                "crc32": source.get("crc32", ""),
                "headline_library_coverage_ratio": round_float(headline_coverage),
                "headline_library_residual_ratio": round_float(headline_residual),
                "headline_coverage_band": coverage_band(headline_coverage),
                "headline_org_conformance_ratio": round_float(headline_conformance),
                "review_priority": review_priority,
                "max_foreign_org_ratio": round_float(max_foreign_ratio),
                "table_form_coverage_ratio": round_float(table_coverage),
                "table_form_residual_ratio": round_float(table_residual),
                "table_org_conformance_ratio": round_float(table_conformance),
                "table_foreign_org_ratio": round_float(table_foreign),
                "table_borrowing_candidate_occurrence_count": table_borrowing_count,
                "table_total_count": safe_int(table.get("total_table_count") if table else ""),
                "text_segment_coverage_ratio": round_float(text_segment_coverage),
                "text_segment_residual_ratio": round_float(text_segment_residual),
                "text_segment_org_conformance_ratio": round_float(text_segment_conformance),
                "text_foreign_org_ratio": round_float(text_foreign),
                "text_copy_review_needed_occurrence_count": copy_review_count,
                "text_segment_occurrence_count": safe_int(text.get("text_segment_occurrence_count") if text else ""),
                "text_shingle_coverage_ratio_diagnostic": round_float(shingle_coverage),
                "table_coverage_status": table_status,
                "text_coverage_status": text_status,
                "interpretation_note": (
                    "combined_table_text_v0; headline_uses_table_forms_and_text_segments; "
                    "shingles_are_diagnostic; residual_is_library_unexplained_not_proven_original"
                ),
            }
        )

    report_rows.sort(key=lambda row: (row["section_code"], row["object_id"], row["bundle_id"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "section_library_report_v0.csv",
        report_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "cohort",
            "crc32",
            "headline_library_coverage_ratio",
            "headline_library_residual_ratio",
            "headline_coverage_band",
            "headline_org_conformance_ratio",
            "review_priority",
            "max_foreign_org_ratio",
            "table_form_coverage_ratio",
            "table_form_residual_ratio",
            "table_org_conformance_ratio",
            "table_foreign_org_ratio",
            "table_borrowing_candidate_occurrence_count",
            "table_total_count",
            "text_segment_coverage_ratio",
            "text_segment_residual_ratio",
            "text_segment_org_conformance_ratio",
            "text_foreign_org_ratio",
            "text_copy_review_needed_occurrence_count",
            "text_segment_occurrence_count",
            "text_shingle_coverage_ratio_diagnostic",
            "table_coverage_status",
            "text_coverage_status",
            "interpretation_note",
        ],
    )

    coverage_by_section: dict[str, list[float]] = defaultdict(list)
    residual_by_section: dict[str, list[float]] = defaultdict(list)
    conformance_by_section: dict[str, list[float]] = defaultdict(list)
    priority_counts = Counter(row["review_priority"] for row in report_rows)
    band_counts = Counter(row["headline_coverage_band"] for row in report_rows)
    cohort_coverage: dict[str, list[float]] = defaultdict(list)
    for row in report_rows:
        section = row["section_code"]
        coverage_by_section[section].append(float(row["headline_library_coverage_ratio"]))
        residual_by_section[section].append(float(row["headline_library_residual_ratio"]))
        conformance_by_section[section].append(float(row["headline_org_conformance_ratio"]))
        cohort_coverage[row["cohort"]].append(float(row["headline_library_coverage_ratio"]))

    write_json(
        output_dir / "section_library_report_v0.json",
        {
            "schema_version": "section_library_report_v0",
            "generated_at": generated_at,
            "table_coverage_path": str(table_coverage_path),
            "text_coverage_path": str(text_coverage_path),
            "output_dir": str(output_dir),
            "document_count": len(report_rows),
            "missing_table_coverage_rows": missing_table,
            "missing_text_coverage_rows": missing_text,
            "review_priority_counts": dict(sorted(priority_counts.items())),
            "headline_coverage_band_counts": dict(sorted(band_counts.items())),
            "section_median_headline_library_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(coverage_by_section.items())
            },
            "section_median_headline_library_residual_ratio": {
                key: round_float(median(values)) for key, values in sorted(residual_by_section.items())
            },
            "section_median_headline_org_conformance_ratio": {
                key: round_float(median(values)) for key, values in sorted(conformance_by_section.items())
            },
            "cohort_median_headline_library_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(cohort_coverage.items())
            },
            "files": {
                "section_report": "section_library_report_v0.csv",
            },
            "modeling_rules": [
                "headline coverage is an unweighted mean of available table-form coverage and text-segment coverage.",
                "text shingles are diagnostic only and are not included in headline coverage.",
                "residual means unexplained by the v0 library layers, not proven original authorship.",
                "review_priority is a triage hint, not a legal conclusion.",
                "table and text source metrics remain available as separate columns.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build combined section library report v0.")
    parser.add_argument("--table-coverage", type=Path, default=DEFAULT_TABLE_COVERAGE)
    parser.add_argument("--text-coverage", type=Path, default=DEFAULT_TEXT_COVERAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    build(args.table_coverage, args.text_coverage, args.output_dir)


if __name__ == "__main__":
    main()
