#!/usr/bin/env python3
"""Build section-level coverage over typical element candidates v0.

The coverage layer is the first consumer-facing projection of the candidate
library: for each section document it reports which table-form candidates are
present, how much of the table layer is explained by the library, and whether
the matched forms look expected for the document cohort.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_CANDIDATE_DIR = Path(r"E:\output\DocSpectrum\typical_element_candidates_v0")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\typical_element_coverage_v0")


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


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def parse_cohort(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("Cohort must use NAME=EXPORT_ROOT format.")
    name, path = raw.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("Cohort name must not be empty.")
    return name, Path(path.strip())


def load_object_cohorts(cohorts: list[tuple[str, Path]]) -> tuple[dict[str, str], dict[str, int]]:
    object_to_cohort: dict[str, str] = {}
    cohort_counts: dict[str, int] = {}
    collisions: dict[str, set[str]] = defaultdict(set)
    for cohort_name, export_root in cohorts:
        object_ids = sorted(path.name for path in export_root.iterdir() if path.is_dir())
        cohort_counts[cohort_name] = len(object_ids)
        for object_id in object_ids:
            if object_id in object_to_cohort and object_to_cohort[object_id] != cohort_name:
                collisions[object_id].update({object_to_cohort[object_id], cohort_name})
            object_to_cohort[object_id] = cohort_name
    if collisions:
        details = ", ".join(f"{key}: {sorted(value)}" for key, value in sorted(collisions.items())[:10])
        raise ValueError(f"Object ids are not unique across cohorts: {details}")
    return object_to_cohort, cohort_counts


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def candidate_matches_expected_org(candidate: dict[str, str], document_cohort: str) -> bool:
    if document_cohort in {"", "UNKNOWN"}:
        return False
    if candidate.get("org_distinctiveness_class") == "cross_org_common":
        return True
    return candidate.get("dominant_org") == document_cohort


def candidate_matches_foreign_org(candidate: dict[str, str], document_cohort: str) -> bool:
    if document_cohort in {"", "UNKNOWN"}:
        return False
    if candidate.get("org_distinctiveness_class") == "cross_org_common":
        return False
    dominant_org = candidate.get("dominant_org")
    return bool(dominant_org and dominant_org != document_cohort)


def build(
    base_dir: Path,
    candidate_dir: Path,
    output_dir: Path,
    cohorts: list[tuple[str, Path]],
    candidate_statuses: set[str],
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_object_counts = load_object_cohorts(cohorts)
    documents = [row for row in read_csv(base_dir / "documents_index.csv") if row.get("section_code") != "UNKNOWN"]
    tables = [row for row in read_csv(base_dir / "table_signatures_v0.csv") if row.get("layout_signature")]
    candidates = read_csv(candidate_dir / "typical_element_candidates_v0.csv")

    candidates_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidates:
        if row.get("candidate_status") not in candidate_statuses:
            continue
        key = (row["section_code"], row["signature_group_hash"])
        candidates_by_key[key] = row

    tables_by_doc: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in tables:
        tables_by_doc[(row["object_id"], row["bundle_id"])].append(row)

    coverage_rows: list[dict[str, Any]] = []
    for doc in sorted(documents, key=lambda row: (row["section_code"], row["object_id"], row["bundle_id"])):
        doc_key = (doc["object_id"], doc["bundle_id"])
        section_code = doc["section_code"]
        document_cohort = object_to_cohort.get(doc["object_id"], "UNKNOWN")
        table_rows = tables_by_doc.get(doc_key, [])
        total_tables = len(table_rows)
        matched_occurrences = 0
        meaningful_occurrences = 0
        trivial_occurrences = 0
        expected_occurrences = 0
        foreign_occurrences = 0
        borrowing_occurrences = 0
        candidate_ids: Counter[str] = Counter()
        meaningful_candidate_ids: set[str] = set()
        class_counts: Counter[str] = Counter()
        org_counts: Counter[str] = Counter()
        status_counts: Counter[str] = Counter()

        for table in table_rows:
            candidate = candidates_by_key.get((section_code, table["layout_signature"]))
            if not candidate:
                continue
            matched_occurrences += 1
            candidate_id = candidate["candidate_id"]
            candidate_ids[candidate_id] += 1
            class_counts[candidate.get("candidate_class", "")] += 1
            org_counts[candidate.get("org_distinctiveness_class", "")] += 1
            status_counts[candidate.get("candidate_status", "")] += 1

            if candidate.get("candidate_class") == "borrowing_candidate":
                borrowing_occurrences += 1
            if candidate.get("triviality_status") == "trivial_micro_form":
                trivial_occurrences += 1
            else:
                meaningful_occurrences += 1
                meaningful_candidate_ids.add(candidate_id)

            if candidate_matches_expected_org(candidate, document_cohort):
                expected_occurrences += 1
            elif candidate_matches_foreign_org(candidate, document_cohort):
                foreign_occurrences += 1

        residual_tables = total_tables - meaningful_occurrences
        sorted_candidate_ids = sorted(candidate_ids)
        top_candidate_ids = sorted(candidate_ids.items(), key=lambda item: (-item[1], item[0]))[:50]
        coverage_rows.append(
            {
                "object_id": doc["object_id"],
                "bundle_id": doc["bundle_id"],
                "section_code": section_code,
                "cohort": document_cohort,
                "crc32": doc.get("crc32"),
                "total_table_count": total_tables,
                "matched_table_form_occurrence_count": matched_occurrences,
                "meaningful_table_form_occurrence_count": meaningful_occurrences,
                "trivial_table_form_occurrence_count": trivial_occurrences,
                "table_form_coverage_ratio": round_float(ratio(meaningful_occurrences, total_tables)),
                "table_form_residual_count": residual_tables,
                "table_form_residual_ratio": round_float(ratio(residual_tables, total_tables)),
                "distinct_candidate_count": len(candidate_ids),
                "distinct_meaningful_candidate_count": len(meaningful_candidate_ids),
                "expected_org_form_occurrence_count": expected_occurrences,
                "foreign_org_form_occurrence_count": foreign_occurrences,
                "org_form_conformance_ratio": round_float(ratio(expected_occurrences, matched_occurrences)),
                "foreign_org_form_ratio": round_float(ratio(foreign_occurrences, matched_occurrences)),
                "borrowing_candidate_occurrence_count": borrowing_occurrences,
                "cross_org_common_occurrence_count": org_counts.get("cross_org_common", 0),
                "org_distinctive_occurrence_count": org_counts.get("org_distinctive", 0),
                "org_specific_occurrence_count": org_counts.get("org_specific", 0),
                "typical_form_occurrence_count": class_counts.get("typical_form", 0),
                "candidate_status_counts": "|".join(f"{key}:{value}" for key, value in sorted(status_counts.items())),
                "candidate_ids": "|".join(sorted_candidate_ids[:100]),
                "candidate_ids_truncated": len(sorted_candidate_ids) > 100,
                "top_candidate_occurrences": "|".join(f"{key}:{value}" for key, value in top_candidate_ids),
                "coverage_status": "no_tables" if total_tables == 0 else "measured",
                "interpretation_note": "table_form_only; residual_is_unexplained_by_v0_library_not_proven_original",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "typical_element_section_coverage_v0.csv",
        coverage_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "cohort",
            "crc32",
            "total_table_count",
            "matched_table_form_occurrence_count",
            "meaningful_table_form_occurrence_count",
            "trivial_table_form_occurrence_count",
            "table_form_coverage_ratio",
            "table_form_residual_count",
            "table_form_residual_ratio",
            "distinct_candidate_count",
            "distinct_meaningful_candidate_count",
            "expected_org_form_occurrence_count",
            "foreign_org_form_occurrence_count",
            "org_form_conformance_ratio",
            "foreign_org_form_ratio",
            "borrowing_candidate_occurrence_count",
            "cross_org_common_occurrence_count",
            "org_distinctive_occurrence_count",
            "org_specific_occurrence_count",
            "typical_form_occurrence_count",
            "candidate_status_counts",
            "candidate_ids",
            "candidate_ids_truncated",
            "top_candidate_occurrences",
            "coverage_status",
            "interpretation_note",
        ],
    )

    coverage_by_section = defaultdict(list)
    residual_by_section = defaultdict(list)
    conformance_by_section = defaultdict(list)
    for row in coverage_rows:
        if row["coverage_status"] != "measured":
            continue
        coverage_by_section[row["section_code"]].append(float(row["table_form_coverage_ratio"]))
        residual_by_section[row["section_code"]].append(float(row["table_form_residual_ratio"]))
        conformance_by_section[row["section_code"]].append(float(row["org_form_conformance_ratio"]))

    def median(values: list[float]) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    write_json(
        output_dir / "typical_element_section_coverage_v0.json",
        {
            "schema_version": "typical_element_section_coverage_v0",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "candidate_dir": str(candidate_dir),
            "output_dir": str(output_dir),
            "candidate_statuses": sorted(candidate_statuses),
            "cohorts": {name: str(path) for name, path in cohorts},
            "cohort_object_counts": cohort_object_counts,
            "document_count": len(coverage_rows),
            "measured_document_count": sum(1 for row in coverage_rows if row["coverage_status"] == "measured"),
            "section_median_table_form_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(coverage_by_section.items())
            },
            "section_median_table_form_residual_ratio": {
                key: round_float(median(values)) for key, values in sorted(residual_by_section.items())
            },
            "section_median_org_form_conformance_ratio": {
                key: round_float(median(values)) for key, values in sorted(conformance_by_section.items())
            },
            "files": {
                "section_coverage": "typical_element_section_coverage_v0.csv",
            },
            "modeling_rules": [
                "coverage is table-form-only in v0 and must not be read as full section originality.",
                "residual means unexplained by the v0 table-form library, not proven original authorship.",
                "expected organization forms are cross-org common forms plus forms whose dominant org matches the document cohort.",
                "foreign organization forms are non-common forms whose dominant org differs from the document cohort.",
                "diagnostic trivial forms can be included or excluded through candidate_statuses.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build section coverage over typical element candidates v0.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--candidate-status",
        action="append",
        default=["candidate"],
        help="Candidate status to include. Repeat to include diagnostic_trivial.",
    )
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat for each organization/cohort.",
    )
    args = parser.parse_args()
    build(
        args.base_dir,
        args.candidate_dir,
        args.output_dir,
        args.cohort,
        set(args.candidate_status),
    )


if __name__ == "__main__":
    main()
