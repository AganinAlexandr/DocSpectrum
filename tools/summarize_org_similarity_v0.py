#!/usr/bin/env python3
"""Summarize within/cross-cohort similarity from pairwise comparison results.

The tool is intentionally domain-light: cohorts are supplied as export roots
whose first-level directories are object_id values. This keeps the core
comparison neutral while allowing research checks for organization handwriting.
"""

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


def pair_type(left_cohort: str | None, right_cohort: str | None) -> str:
    if not left_cohort or not right_cohort:
        return "unknown"
    if left_cohort == right_cohort:
        return f"within_{left_cohort.lower()}"
    names = "_".join(sorted((left_cohort.lower(), right_cohort.lower())))
    return f"cross_{names}"


def summarize_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "pair_count": 0,
            "median": None,
            "mean": None,
            "p10": None,
            "p90": None,
            "min": None,
            "max": None,
        }
    return {
        "pair_count": len(values),
        "median": round_float(statistics.median(values)),
        "mean": round_float(statistics.fmean(values)),
        "p10": round_float(percentile(values, 0.10)),
        "p90": round_float(percentile(values, 0.90)),
        "min": round_float(min(values)),
        "max": round_float(max(values)),
    }


def build_summary(
    comparison_csv: Path,
    cohorts: list[tuple[str, Path]],
    output_dir: Path,
    metric_column: str,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_counts = load_object_cohorts(cohorts)
    rows = read_csv(comparison_csv)
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    pair_type_counts: defaultdict[str, int] = defaultdict(int)
    unknown_pairs = 0

    for row in rows:
        value = safe_float(row.get(metric_column))
        if value is None:
            continue
        left_cohort = object_to_cohort.get(row.get("left_object_id", ""))
        right_cohort = object_to_cohort.get(row.get("right_object_id", ""))
        current_pair_type = pair_type(left_cohort, right_cohort)
        if current_pair_type == "unknown":
            unknown_pairs += 1
        pair_type_counts[current_pair_type] += 1
        grouped[(current_pair_type, row["section_code"])].append(value)

    summary_rows = []
    for (current_pair_type, section_code), values in sorted(grouped.items()):
        stats = summarize_values(values)
        summary_rows.append(
            {
                "pair_type": current_pair_type,
                "section_code": section_code,
                **stats,
            }
        )

    pair_types = sorted({row["pair_type"] for row in summary_rows})
    within_types = [name for name in pair_types if name.startswith("within_")]
    cross_types = [name for name in pair_types if name.startswith("cross_")]
    section_codes = sorted({row["section_code"] for row in summary_rows})
    median_by_key = {(row["pair_type"], row["section_code"]): row["median"] for row in summary_rows}
    separation_rows = []
    if len(within_types) >= 2 and cross_types:
        primary_cross = cross_types[0]
        for section_code in section_codes:
            within_medians = [
                median_by_key[(within_type, section_code)]
                for within_type in within_types
                if median_by_key.get((within_type, section_code)) is not None
            ]
            cross_median = median_by_key.get((primary_cross, section_code))
            if not within_medians or cross_median is None:
                continue
            within_avg = statistics.fmean(within_medians)
            separation_rows.append(
                {
                    "section_code": section_code,
                    "cross_pair_type": primary_cross,
                    "within_avg_median": round_float(within_avg),
                    "cross_median": round_float(cross_median),
                    "separation_gap": round_float(within_avg - cross_median),
                    **{
                        f"{within_type}_median": median_by_key.get((within_type, section_code))
                        for within_type in within_types
                    },
                }
            )
        separation_rows.sort(key=lambda row: (-row["separation_gap"], row["section_code"]))

    write_csv(
        output_dir / "org_pair_similarity_summary_v0.csv",
        summary_rows,
        ["pair_type", "section_code", "pair_count", "median", "mean", "p10", "p90", "min", "max"],
    )
    separation_fieldnames = ["section_code", "cross_pair_type", "within_avg_median", "cross_median", "separation_gap"]
    separation_fieldnames.extend(f"{within_type}_median" for within_type in within_types)
    write_csv(output_dir / "org_separation_v0.csv", separation_rows, separation_fieldnames)
    write_json(
        output_dir / "cross_org_research_v0.json",
        {
            "schema_version": "cross_org_research_v0",
            "generated_at": generated_at,
            "comparison_csv": str(comparison_csv),
            "metric_column": metric_column,
            "cohorts": {name: str(path) for name, path in cohorts},
            "cohort_object_counts": cohort_counts,
            "comparison_row_count": len(rows),
            "scored_pair_count": sum(pair_type_counts.values()),
            "pair_type_counts": dict(sorted(pair_type_counts.items())),
            "unknown_pair_count": unknown_pairs,
            "summary_csv": str(output_dir / "org_pair_similarity_summary_v0.csv"),
            "separation_csv": str(output_dir / "org_separation_v0.csv"),
            "modeling_rules": [
                "Cohort labels are research metadata and are not used by pairwise scoring.",
                "Within/cross summaries are computed after pairwise comparison from object_id membership.",
                "Separation gap is diagnostic until reviewed on a committed packet.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize within/cross organization similarity.")
    parser.add_argument("--comparison-csv", type=Path, default=DEFAULT_COMPARISON_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metric-column", default="idf_similarity_v0_3")
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
    build_summary(args.comparison_csv, args.cohort, args.output_dir, args.metric_column)


if __name__ == "__main__":
    main()
