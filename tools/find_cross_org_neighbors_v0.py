#!/usr/bin/env python3
"""Find nearest cross-cohort neighbors from pairwise comparison results."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_COMPARISON_CSV = Path(
    r"E:\output\DocSpectrum\comparison_results_v0_3_rpsk35_nk34\comparison_results_v0_3.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\cross_org_research_v0")


NEIGHBOR_AXIS_COLUMNS = [
    "text_segment_idf_jaccard",
    "text_word_shingle_idf_jaccard",
    "table_cell_text_idf_jaccard",
    "table_layout_signature_idf_jaccard",
    "table_content_signature_idf_jaccard",
    "page_signature_idf_jaccard",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def round_float(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


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


def document_key(row: dict[str, str], side: str) -> tuple[str, str, str]:
    return row[f"{side}_object_id"], row[f"{side}_bundle_id"], row["section_code"]


def format_doc_key(key: tuple[str, str, str]) -> str:
    return "||".join(key)


def build_candidate(
    row: dict[str, str],
    query_side: str,
    query_cohort: str,
    neighbor_cohort: str,
    metric_column: str,
) -> dict[str, Any]:
    neighbor_side = "right" if query_side == "left" else "left"
    candidate = {
        "query_cohort": query_cohort,
        "query_object_id": row[f"{query_side}_object_id"],
        "query_bundle_id": row[f"{query_side}_bundle_id"],
        "section_code": row["section_code"],
        "neighbor_cohort": neighbor_cohort,
        "neighbor_object_id": row[f"{neighbor_side}_object_id"],
        "neighbor_bundle_id": row[f"{neighbor_side}_bundle_id"],
        "score": safe_float(row.get(metric_column)),
        "pair_id": row["pair_id"],
    }
    for column in NEIGHBOR_AXIS_COLUMNS:
        candidate[column] = safe_float(row.get(column))
    return candidate


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "pair_count": 0,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "pair_count": len(values),
        "median": round_float(statistics.median(values)),
        "p90": round_float(percentile(values, 0.90)),
        "p95": round_float(percentile(values, 0.95)),
        "p99": round_float(percentile(values, 0.99)),
        "max": round_float(max(values)),
    }


def find_neighbors(
    comparison_csv: Path,
    cohorts: list[tuple[str, Path]],
    output_dir: Path,
    metric_column: str,
    top_n: int,
    top_pairs_per_section: int,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_counts = load_object_cohorts(cohorts)
    rows = read_csv(comparison_csv)
    candidates_by_doc: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    cross_pairs_by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    section_values: dict[str, list[float]] = defaultdict(list)
    cross_pair_count = 0

    for row in rows:
        score = safe_float(row.get(metric_column))
        if score is None:
            continue
        left_cohort = object_to_cohort.get(row.get("left_object_id", ""))
        right_cohort = object_to_cohort.get(row.get("right_object_id", ""))
        if not left_cohort or not right_cohort or left_cohort == right_cohort:
            continue

        cross_pair_count += 1
        section_values[row["section_code"]].append(score)
        cross_pairs_by_section[row["section_code"]].append(row)
        left_key = document_key(row, "left")
        right_key = document_key(row, "right")
        candidates_by_doc[left_key].append(build_candidate(row, "left", left_cohort, right_cohort, metric_column))
        candidates_by_doc[right_key].append(build_candidate(row, "right", right_cohort, left_cohort, metric_column))

    neighbor_rows = []
    for query_key, candidates in sorted(candidates_by_doc.items(), key=lambda item: format_doc_key(item[0])):
        candidates.sort(key=lambda item: (-(item["score"] or 0.0), item["neighbor_object_id"], item["neighbor_bundle_id"]))
        for rank, candidate in enumerate(candidates[:top_n], start=1):
            neighbor_rows.append({"neighbor_rank": rank, **{key: round_float(value) if isinstance(value, float) else value for key, value in candidate.items()}})

    top_pair_rows = []
    for section_code, section_rows in sorted(cross_pairs_by_section.items()):
        section_rows.sort(key=lambda row: (-(safe_float(row.get(metric_column)) or 0.0), row["pair_id"]))
        for rank, row in enumerate(section_rows[:top_pairs_per_section], start=1):
            left_cohort = object_to_cohort[row["left_object_id"]]
            right_cohort = object_to_cohort[row["right_object_id"]]
            top_pair = {
                "section_code": section_code,
                "section_rank": rank,
                "score": round_float(safe_float(row.get(metric_column))),
                "left_cohort": left_cohort,
                "left_object_id": row["left_object_id"],
                "left_bundle_id": row["left_bundle_id"],
                "right_cohort": right_cohort,
                "right_object_id": row["right_object_id"],
                "right_bundle_id": row["right_bundle_id"],
                "pair_id": row["pair_id"],
            }
            for column in NEIGHBOR_AXIS_COLUMNS:
                top_pair[column] = round_float(safe_float(row.get(column)))
            top_pair_rows.append(top_pair)

    section_summary_rows = [
        {"section_code": section_code, **summarize_values(values)}
        for section_code, values in sorted(section_values.items())
    ]

    neighbor_fieldnames = [
        "neighbor_rank",
        "query_cohort",
        "query_object_id",
        "query_bundle_id",
        "section_code",
        "neighbor_cohort",
        "neighbor_object_id",
        "neighbor_bundle_id",
        "score",
        "pair_id",
        *NEIGHBOR_AXIS_COLUMNS,
    ]
    top_pair_fieldnames = [
        "section_code",
        "section_rank",
        "score",
        "left_cohort",
        "left_object_id",
        "left_bundle_id",
        "right_cohort",
        "right_object_id",
        "right_bundle_id",
        "pair_id",
        *NEIGHBOR_AXIS_COLUMNS,
    ]
    summary_fieldnames = ["section_code", "pair_count", "median", "p90", "p95", "p99", "max"]
    write_csv(output_dir / "cross_org_nearest_neighbors_v0.csv", neighbor_rows, neighbor_fieldnames)
    write_csv(output_dir / "cross_org_top_pairs_v0.csv", top_pair_rows, top_pair_fieldnames)
    write_csv(output_dir / "cross_org_section_extremes_v0.csv", section_summary_rows, summary_fieldnames)
    write_json(
        output_dir / "cross_org_neighbors_v0.json",
        {
            "schema_version": "cross_org_neighbors_v0",
            "generated_at": generated_at,
            "comparison_csv": str(comparison_csv),
            "metric_column": metric_column,
            "cohorts": {name: str(path) for name, path in cohorts},
            "cohort_object_counts": cohort_counts,
            "cross_pair_count": cross_pair_count,
            "document_with_neighbor_count": len(candidates_by_doc),
            "top_n_per_document": top_n,
            "top_pairs_per_section": top_pairs_per_section,
            "nearest_neighbors_csv": str(output_dir / "cross_org_nearest_neighbors_v0.csv"),
            "top_pairs_csv": str(output_dir / "cross_org_top_pairs_v0.csv"),
            "section_extremes_csv": str(output_dir / "cross_org_section_extremes_v0.csv"),
            "modeling_rules": [
                "Nearest-neighbor diagnostics are computed after pairwise scoring.",
                "Cohort labels are not used by the scoring layer.",
                "High cross-cohort neighbors are candidates for manual/domain inspection, not proof of borrowing.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Find nearest cross-cohort neighbors.")
    parser.add_argument("--comparison-csv", type=Path, default=DEFAULT_COMPARISON_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metric-column", default="idf_similarity_v0_3")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--top-pairs-per-section", type=int, default=20)
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat at least twice.",
    )
    args = parser.parse_args()
    if len(args.cohort) < 2:
        raise SystemExit("At least two --cohort values are required.")
    find_neighbors(args.comparison_csv, args.cohort, args.output_dir, args.metric_column, args.top_n, args.top_pairs_per_section)


if __name__ == "__main__":
    main()
