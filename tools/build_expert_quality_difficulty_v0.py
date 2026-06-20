#!/usr/bin/env python3
"""Build expert-independent spectral difficulty proxies for experiment C.

Difficulty is computed only from pre-expertise PSE structure. Expert identity
and review outcomes are joined afterwards for diagnostic stratification.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from build_expert_quality_session_variance_v0 import (
    build_session_rows,
    merge_object_section_rows,
)


DEFAULT_ARENA_PAIRS = Path(
    r"E:\output\DocSpectrum\expert_quality_experiment_c_v0"
    r"\expert_quality_arena_pairs_v0.csv"
)
DEFAULT_REGISTRY_ROWS = Path(
    r"E:\output\DocSpectrum\expert_quality_experiment_c_v0"
    r"\expert_quality_registry_rows_v0.csv"
)
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\expert_quality_difficulty_v0"
)
DIFFICULTY_AXES = (
    "page_count",
    "element_count",
    "elements_per_page",
    "structural_elements_per_page",
    "table_cells_per_page",
)


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
    return int(safe_float(value, default))


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def percentile_ranks(values: list[float]) -> list[float]:
    """Midrank percentiles in [0, 1], with tied values sharing one rank."""
    if not values:
        return []
    if len(values) == 1:
        return [0.5]
    ordered = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][0] == ordered[cursor][0]:
            end += 1
        average_rank = (cursor + end - 1) / 2
        percentile = average_rank / (len(values) - 1)
        for _, original_index in ordered[cursor:end]:
            result[original_index] = percentile
        cursor = end
    return result


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    left_rank = percentile_ranks(left)
    right_rank = percentile_ranks(right)
    left_mean = mean(left_rank)
    right_mean = mean(right_rank)
    numerator = sum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left_rank, right_rank)
    )
    left_var = sum((value - left_mean) ** 2 for value in left_rank)
    right_var = sum((value - right_mean) ** 2 for value in right_rank)
    denominator = math.sqrt(left_var * right_var)
    return numerator / denominator if denominator else None


def unique_arena_documents(arena_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    documents: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in arena_rows:
        for side in ("left", "right"):
            key = (
                row[f"{side}_object_id"],
                row["section_code"],
                row[f"{side}_bundle_id"],
            )
            documents[key] = {
                "group_id": row["group_id"],
                "organization": row["organization"],
                "work_type": row["work_type"],
                "section_code": row["section_code"],
                "object_id": row[f"{side}_object_id"],
                "bundle_id": row[f"{side}_bundle_id"],
            }
    return list(documents.values())


def bundle_difficulty(bundle_dir: Path) -> dict[str, Any]:
    page_summary = read_csv(bundle_dir / "page_summary.csv")
    totals: Counter[str] = Counter()
    page_elements: list[int] = []
    for row in page_summary:
        elements = safe_int(row.get("element_count"))
        page_elements.append(elements)
        for key in (
            "text_count",
            "line_count",
            "frame_count",
            "image_count",
            "other_vector_count",
            "table_count",
            "table_cell_count",
        ):
            totals[key] += safe_int(row.get(key))
        totals["element_count"] += elements

    page_count = len(page_summary)
    structural_elements = (
        totals["line_count"]
        + totals["frame_count"]
        + totals["image_count"]
        + totals["other_vector_count"]
    )
    component_counts = [
        totals["text_count"],
        totals["line_count"],
        totals["frame_count"],
        totals["image_count"],
        totals["other_vector_count"],
        totals["table_count"],
    ]
    component_total = sum(component_counts)
    entropy = 0.0
    if component_total:
        for count in component_counts:
            if count:
                share = count / component_total
                entropy -= share * math.log(share)
        entropy /= math.log(len(component_counts))

    return {
        "page_count": page_count,
        "element_count": totals["element_count"],
        "elements_per_page": totals["element_count"] / page_count if page_count else 0.0,
        "structural_element_count": structural_elements,
        "structural_elements_per_page": structural_elements / page_count if page_count else 0.0,
        "text_elements_per_page": totals["text_count"] / page_count if page_count else 0.0,
        "table_count": totals["table_count"],
        "table_cells_per_page": totals["table_cell_count"] / page_count if page_count else 0.0,
        "max_page_element_count": max(page_elements) if page_elements else 0,
        "median_page_element_count": median(page_elements) if page_elements else 0.0,
        "component_mix_entropy": entropy,
    }


def add_section_relative_percentiles(rows: list[dict[str, Any]]) -> None:
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_section[str(row["section_code"])].append(row)
    for section_rows in by_section.values():
        for axis in DIFFICULTY_AXES:
            ranks = percentile_ranks(
                [math.log1p(float(row[axis])) for row in section_rows]
            )
            for row, rank in zip(section_rows, ranks):
                row[f"{axis}_percentile_within_section"] = round_float(rank)
        for row in section_rows:
            percentiles = [
                float(row[f"{axis}_percentile_within_section"])
                for axis in DIFFICULTY_AXES
            ]
            row["spectral_difficulty_percentile_v0"] = round_float(mean(percentiles))
            row["difficulty_band_v0"] = (
                "low"
                if row["spectral_difficulty_percentile_v0"] < 1 / 3
                else "high"
                if row["spectral_difficulty_percentile_v0"] >= 2 / 3
                else "medium"
            )


def build_document_rows(
    arena_rows: list[dict[str, str]],
    export_root: Path,
) -> list[dict[str, Any]]:
    output = []
    for document in unique_arena_documents(arena_rows):
        profile = bundle_difficulty(export_root / document["bundle_id"])
        output.append({**document, **profile})
    add_section_relative_percentiles(output)
    return sorted(
        output,
        key=lambda row: (row["section_code"], row["organization"], row["object_id"]),
    )


def join_review_rows(
    document_rows: list[dict[str, Any]],
    registry_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    documents: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in document_rows:
        documents[
            (
                str(row["object_id"]),
                str(row["organization"]),
                str(row["work_type"]),
                str(row["section_code"]),
            )
        ] = row

    merged_registry = merge_object_section_rows(registry_rows)
    output = []
    for review in merged_registry:
        document = documents.get(
            (
                str(review["object_id"]),
                str(review["organization"]),
                str(review["work_type"]),
                str(review["section_code"]),
            )
        )
        if not document:
            continue
        output.append(
            {
                **review,
                "bundle_id": document["bundle_id"],
                "page_count": document["page_count"],
                "element_count": document["element_count"],
                "elements_per_page": round_float(document["elements_per_page"]),
                "structural_elements_per_page": round_float(
                    document["structural_elements_per_page"]
                ),
                "table_cells_per_page": round_float(document["table_cells_per_page"]),
                "spectral_difficulty_percentile_v0": document[
                    "spectral_difficulty_percentile_v0"
                ],
                "difficulty_band_v0": document["difficulty_band_v0"],
            }
        )
    return output


def build_session_difficulty(
    review_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    session_rows = build_session_rows(review_rows)
    reviews_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        key = "|".join(
            [
                str(row["expert_hash"]),
                str(row["organization"]),
                str(row["work_type"]),
                str(row["session_start_date"]),
            ]
        )
        reviews_by_session[key].append(row)

    output = []
    for session in session_rows:
        reviews = reviews_by_session[session["session_id"]]
        difficulty = [
            float(row["spectral_difficulty_percentile_v0"]) for row in reviews
        ]
        pages = [int(row["page_count"]) for row in reviews]
        elements = [int(row["element_count"]) for row in reviews]
        output.append(
            {
                **session,
                "difficulty_document_count": len(reviews),
                "session_difficulty_mean_v0": round_float(mean(difficulty)),
                "session_difficulty_median_v0": round_float(median(difficulty)),
                "session_page_count_total": sum(pages),
                "session_element_count_total": sum(elements),
            }
        )
    return output


def summarize_roles(session_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in session_rows:
        role = str(row["expert_anchor_role"])
        if role and role != "unlabeled":
            grouped[role].append(row)

    output = []
    for role, rows in sorted(grouped.items()):
        difficulty = [float(row["session_difficulty_mean_v0"]) for row in rows]
        clean = [float(row["clean_share_all_sections"]) for row in rows]
        correlation = spearman(difficulty, clean)
        by_band: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            value = float(row["session_difficulty_mean_v0"])
            band = "low" if value < 1 / 3 else "high" if value >= 2 / 3 else "medium"
            by_band[band].append(float(row["clean_share_all_sections"]))
        output.append(
            {
                "expert_anchor_role": role,
                "session_count": len(rows),
                "difficulty_mean": round_float(mean(difficulty)),
                "difficulty_median": round_float(median(difficulty)),
                "spearman_difficulty_vs_clean_share": (
                    round_float(correlation) if correlation is not None else ""
                ),
                "low_difficulty_session_count": len(by_band["low"]),
                "low_difficulty_clean_share_mean": (
                    round_float(mean(by_band["low"])) if by_band["low"] else ""
                ),
                "medium_difficulty_session_count": len(by_band["medium"]),
                "medium_difficulty_clean_share_mean": (
                    round_float(mean(by_band["medium"])) if by_band["medium"] else ""
                ),
                "high_difficulty_session_count": len(by_band["high"]),
                "high_difficulty_clean_share_mean": (
                    round_float(mean(by_band["high"])) if by_band["high"] else ""
                ),
                "interpretation_status": "diagnostic_not_causal",
            }
        )
    return output


def build(
    arena_pairs_path: Path,
    registry_rows_path: Path,
    export_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    arena_rows = read_csv(arena_pairs_path)
    registry_rows = read_csv(registry_rows_path)
    documents = build_document_rows(arena_rows, export_root)
    reviews = join_review_rows(documents, registry_rows)
    sessions = build_session_difficulty(reviews)
    role_summary = summarize_roles(sessions)

    output_dir.mkdir(parents=True, exist_ok=True)
    document_fields = [
        "group_id",
        "organization",
        "work_type",
        "section_code",
        "object_id",
        "bundle_id",
        "page_count",
        "element_count",
        "elements_per_page",
        "structural_element_count",
        "structural_elements_per_page",
        "text_elements_per_page",
        "table_count",
        "table_cells_per_page",
        "max_page_element_count",
        "median_page_element_count",
        "component_mix_entropy",
    ]
    document_fields += [
        f"{axis}_percentile_within_section" for axis in DIFFICULTY_AXES
    ]
    document_fields += ["spectral_difficulty_percentile_v0", "difficulty_band_v0"]
    write_csv(
        output_dir / "expert_quality_document_difficulty_v0.csv",
        documents,
        document_fields,
    )
    write_csv(
        output_dir / "expert_quality_review_difficulty_v0.csv",
        reviews,
        [
            "expert_hash",
            "expert_anchor_role",
            "expert_quality_class",
            "organization",
            "work_type",
            "session_start_date",
            "object_id",
            "section_code",
            "bundle_id",
            "has_first_round_remark",
            "clean_first_round_pass",
            "page_count",
            "element_count",
            "elements_per_page",
            "structural_elements_per_page",
            "table_cells_per_page",
            "spectral_difficulty_percentile_v0",
            "difficulty_band_v0",
        ],
    )
    write_csv(
        output_dir / "expert_quality_session_difficulty_v0.csv",
        sessions,
        [
            "session_id",
            "expert_hash",
            "expert_anchor_role",
            "expert_quality_class",
            "organization",
            "work_type",
            "session_start_date",
            "object_count",
            "section_count",
            "section_codes",
            "clean_pass_count",
            "remark_count",
            "unresolved_outcome_count",
            "classified_outcome_count",
            "classified_outcome_share",
            "clean_share_all_sections",
            "remark_share_all_sections",
            "clean_share_classified",
            "remark_share_classified",
            "session_size_class",
            "difficulty_document_count",
            "session_difficulty_mean_v0",
            "session_difficulty_median_v0",
            "session_page_count_total",
            "session_element_count_total",
        ],
    )
    write_csv(
        output_dir / "expert_quality_difficulty_by_role_v0.csv",
        role_summary,
        [
            "expert_anchor_role",
            "session_count",
            "difficulty_mean",
            "difficulty_median",
            "spearman_difficulty_vs_clean_share",
            "low_difficulty_session_count",
            "low_difficulty_clean_share_mean",
            "medium_difficulty_session_count",
            "medium_difficulty_clean_share_mean",
            "high_difficulty_session_count",
            "high_difficulty_clean_share_mean",
            "interpretation_status",
        ],
    )
    summary = {
        "schema_version": "expert_quality_difficulty_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "arena_pairs": str(arena_pairs_path),
            "registry_rows": str(registry_rows_path),
            "export_root": str(export_root),
        },
        "counts": {
            "arena_pair_count": len(arena_rows),
            "unique_arena_document_count": len(documents),
            "review_difficulty_row_count": len(reviews),
            "session_difficulty_row_count": len(sessions),
            "anchor_role_summary_count": len(role_summary),
        },
        "difficulty_axes": list(DIFFICULTY_AXES),
        "normalization": "log1p_midrank_percentile_within_section_code_then_equal_mean",
        "interpretation": {
            "difficulty": "expert_independent_pre_expertise_structure_proxy",
            "outcome_join": "diagnostic_only_not_causal",
            "remark_recall_normalization": "blocked_until_remark_content",
        },
    }
    write_json(output_dir / "expert_quality_difficulty_v0.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build spectral difficulty proxy for experiment C."
    )
    parser.add_argument("--arena-pairs", type=Path, default=DEFAULT_ARENA_PAIRS)
    parser.add_argument("--registry-rows", type=Path, default=DEFAULT_REGISTRY_ROWS)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build(
        args.arena_pairs,
        args.registry_rows,
        args.export_root,
        args.output_dir,
    )
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
