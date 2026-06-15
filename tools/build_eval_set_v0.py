#!/usr/bin/env python3
"""Build eval scaffolding artifacts for DocSpectrum.

This is a read-only validation layer over existing comparison artifacts. It
does not tune or change scoring weights.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEI_FEATURES = [
    "tei_norm_building_volume_m3",
    "tei_norm_floors_count",
    "tei_norm_height_m",
    "tei_norm_apartments_count",
    "tei_norm_total_area_m2",
    "tei_norm_footprint_area_m2",
]

SECTION_EXPECTATIONS = {
    "АР": {
        "axis_a_bucket": "object_descriptive_high",
        "expected_similarity_rank": 5,
        "axis_a_eval_role": "primary",
    },
    "КР": {
        "axis_a_bucket": "object_descriptive_high",
        "expected_similarity_rank": 5,
        "axis_a_eval_role": "primary",
    },
    "ПОКР": {
        "axis_a_bucket": "object_descriptive_high",
        "expected_similarity_rank": 5,
        "axis_a_eval_role": "primary",
    },
    "ПОС": {
        "axis_a_bucket": "object_descriptive_high",
        "expected_similarity_rank": 5,
        "axis_a_eval_role": "primary",
    },
    "ИОС5.1": {
        "axis_a_bucket": "engineering_medium",
        "expected_similarity_rank": 3,
        "axis_a_eval_role": "primary",
    },
    "ИОС5.5.1": {
        "axis_a_bucket": "engineering_medium",
        "expected_similarity_rank": 3,
        "axis_a_eval_role": "primary",
    },
    "ИОС5.4.1": {
        "axis_a_bucket": "system_solution_low_same_house",
        "expected_similarity_rank": 1,
        "axis_a_eval_role": "primary",
    },
    "ИД": {
        "axis_a_bucket": "boilerplate_high_not_discriminative",
        "expected_similarity_rank": 4,
        "axis_a_eval_role": "diagnostic",
    },
    "СМ": {
        "axis_a_bucket": "estimate_control",
        "expected_similarity_rank": 2,
        "axis_a_eval_role": "diagnostic",
    },
}


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


def safe_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def metric_float(value: Any) -> float:
    parsed = safe_float(value)
    return parsed if parsed is not None else 0.0


def round_float(value: float | None, digits: int = 4) -> float | str:
    if value is None or math.isnan(value):
        return ""
    return round(value, digits)


def mean_stdev(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    return mean, stdev if stdev else 1.0


def percentile_rank(sorted_values: list[float], value: float) -> float:
    if not sorted_values:
        return 0.0
    less_or_equal = sum(1 for item in sorted_values if item <= value)
    return less_or_equal / len(sorted_values)


def rankdata(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        end = position + 1
        while end < len(indexed) and indexed[end][1] == indexed[position][1]:
            end += 1
        average_rank = (position + 1 + end) / 2
        for index in range(position, end):
            ranks[indexed[index][0]] = average_rank
        position = end
    return ranks


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_norm = math.sqrt(sum((a - left_mean) ** 2 for a in left))
    right_norm = math.sqrt(sum((b - right_mean) ** 2 for b in right))
    if not left_norm or not right_norm:
        return None
    return numerator / (left_norm * right_norm)


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    return pearson(rankdata(left), rankdata(right))


def load_objects(path: Path) -> dict[str, dict[str, str]]:
    return {row["object_id"]: row for row in read_csv(path)}


def load_consistency(path: Path) -> dict[str, dict[str, str]]:
    return {row["address_normalized"]: row for row in read_csv(path)}


def build_tei_stats(objects: dict[str, dict[str, str]], object_ids: set[str]) -> dict[str, dict[str, float]]:
    stats = {}
    for feature in TEI_FEATURES:
        values = [
            parsed
            for object_id in object_ids
            if (parsed := safe_float(objects.get(object_id, {}).get(feature))) is not None
        ]
        mean, stdev = mean_stdev(values)
        stats[feature] = {
            "mean": mean,
            "stdev": stdev,
            "count": len(values),
        }
    return stats


def tei_distance(
    left: dict[str, str],
    right: dict[str, str],
    stats: dict[str, dict[str, float]],
) -> tuple[float | None, int, str]:
    squared = []
    used_features = []
    for feature in TEI_FEATURES:
        left_value = safe_float(left.get(feature))
        right_value = safe_float(right.get(feature))
        if left_value is None or right_value is None:
            continue
        stdev = stats[feature]["stdev"] or 1.0
        squared.append(((left_value - right_value) / stdev) ** 2)
        used_features.append(feature)
    if not squared:
        return None, 0, ""
    return math.sqrt(sum(squared) / len(squared)), len(squared), "|".join(used_features)


def choose_tei_bucket(
    same_address: bool,
    distance: float | None,
    near_threshold: float,
    far_threshold: float,
) -> str:
    if same_address:
        return "same_address"
    if distance is None:
        return "tei_unknown"
    if distance <= near_threshold:
        return "near_tei_same_section"
    if distance >= far_threshold:
        return "far_tei_same_section"
    return "mid_tei_same_section"


def build(
    object_registry_path: Path,
    address_consistency_path: Path,
    comparison_v0_3_path: Path,
    output_dir: Path,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    objects = load_objects(object_registry_path)
    consistency_by_address = load_consistency(address_consistency_path)
    comparison_rows = read_csv(comparison_v0_3_path)
    object_ids = {
        row["left_object_id"] for row in comparison_rows
    } | {
        row["right_object_id"] for row in comparison_rows
    }
    tei_stats = build_tei_stats(objects, object_ids)

    section_scores: dict[str, list[float]] = defaultdict(list)
    for row in comparison_rows:
        section_scores[row["section_code"]].append(metric_float(row["idf_similarity_v0_3"]))
    sorted_section_scores = {
        section: sorted(values)
        for section, values in section_scores.items()
    }

    raw_distances = []
    seen_distance_object_pairs = set()
    pair_distance_cache: dict[str, tuple[float | None, int, str, bool]] = {}
    for row in comparison_rows:
        left = objects.get(row["left_object_id"], {})
        right = objects.get(row["right_object_id"], {})
        same_address = bool(left.get("address_normalized")) and (
            left.get("address_normalized") == right.get("address_normalized")
        )
        distance, field_count, used_fields = tei_distance(left, right, tei_stats)
        pair_distance_cache[row["pair_id"]] = (distance, field_count, used_fields, same_address)
        object_pair_key = tuple(sorted((row["left_object_id"], row["right_object_id"])))
        if not same_address and distance is not None and object_pair_key not in seen_distance_object_pairs:
            seen_distance_object_pairs.add(object_pair_key)
            raw_distances.append(distance)

    sorted_distances = sorted(raw_distances)
    near_threshold = sorted_distances[len(sorted_distances) // 4] if sorted_distances else 0.0
    far_threshold = sorted_distances[(len(sorted_distances) * 3) // 4] if sorted_distances else 0.0

    eval_rows: list[dict[str, Any]] = []
    same_address_rows: list[dict[str, Any]] = []
    bucket_counter = Counter()
    consistency_counter = Counter()

    for row in comparison_rows:
        left = objects.get(row["left_object_id"], {})
        right = objects.get(row["right_object_id"], {})
        distance, field_count, used_fields, same_address = pair_distance_cache[row["pair_id"]]
        left_address = left.get("address_normalized", "")
        right_address = right.get("address_normalized", "")
        consistency = consistency_by_address.get(left_address, {}) if same_address else {}
        consistency_status = consistency.get("consistency_status", "")
        same_address_cross_system = same_address and left.get("project_subgroup") != right.get("project_subgroup")
        tei_bucket = choose_tei_bucket(same_address, distance, near_threshold, far_threshold)
        eval_bucket = "same_address_cross_system" if same_address_cross_system else tei_bucket
        expectation = SECTION_EXPECTATIONS.get(
            row["section_code"],
            {
                "axis_a_bucket": "unknown_section",
                "expected_similarity_rank": "",
                "axis_a_eval_role": "excluded",
            },
        )
        metric = metric_float(row["idf_similarity_v0_3"])
        baseline = metric_float(row["combined_similarity_v0_2"])
        section_percentile = percentile_rank(sorted_section_scores[row["section_code"]], metric)
        ground_truth_risk = (
            "tei_inconsistent_same_address"
            if same_address and consistency_status == "inconsistent"
            else "ok"
        )

        eval_row = {
            "pair_id": row["pair_id"],
            "section_code": row["section_code"],
            "left_object_id": row["left_object_id"],
            "right_object_id": row["right_object_id"],
            "left_subgroup": left.get("project_subgroup", ""),
            "right_subgroup": right.get("project_subgroup", ""),
            "left_address_normalized": left_address,
            "right_address_normalized": right_address,
            "same_address": str(same_address).lower(),
            "same_address_cross_system": str(same_address_cross_system).lower(),
            "address_consistency_status": consistency_status,
            "ground_truth_risk": ground_truth_risk,
            "tei_distance_z": round_float(distance),
            "tei_distance_field_count": field_count,
            "tei_distance_features": used_fields,
            "tei_bucket": tei_bucket,
            "eval_bucket": eval_bucket,
            "axis_a_bucket": expectation["axis_a_bucket"],
            "axis_a_eval_role": expectation["axis_a_eval_role"],
            "expected_similarity_rank": expectation["expected_similarity_rank"],
            "idf_similarity_v0_3": round_float(metric),
            "combined_similarity_v0_2": round_float(baseline),
            "section_percentile_v0_3": round_float(section_percentile),
            "page_signature_idf_jaccard": row.get("page_signature_idf_jaccard", ""),
        }
        eval_rows.append(eval_row)
        bucket_counter[eval_bucket] += 1
        if consistency_status:
            consistency_counter[consistency_status] += 1

        if same_address_cross_system:
            same_address_rows.append(eval_row)

    eval_rows.sort(key=lambda row: (row["eval_bucket"], row["section_code"], row["pair_id"]))
    same_address_rows.sort(key=lambda row: (row["left_address_normalized"], row["section_code"], row["pair_id"]))

    primary_axis_a = [
        row for row in same_address_rows
        if row["axis_a_eval_role"] == "primary" and row["ground_truth_risk"] == "ok"
    ]
    axis_a_expected = [float(row["expected_similarity_rank"]) for row in primary_axis_a]
    axis_a_observed = [float(row["idf_similarity_v0_3"]) for row in primary_axis_a]
    axis_a_percentile = [float(row["section_percentile_v0_3"]) for row in primary_axis_a]

    non_same_rows = [
        row for row in eval_rows
        if row["same_address"] == "false" and row["tei_distance_z"] != ""
    ]
    axis_b_distance = [float(row["tei_distance_z"]) for row in non_same_rows]
    axis_b_similarity = [float(row["idf_similarity_v0_3"]) for row in non_same_rows]
    axis_b_baseline = [float(row["combined_similarity_v0_2"]) for row in non_same_rows]

    section_summary_rows = []
    for section_code, rows in sorted(defaultdict(list, {
        section: [row for row in eval_rows if row["section_code"] == section]
        for section in {row["section_code"] for row in eval_rows}
    }).items()):
        same_rows = [row for row in rows if row["same_address_cross_system"] == "true"]
        section_summary_rows.append(
            {
                "section_code": section_code,
                "pair_count": len(rows),
                "same_address_cross_system_count": len(same_rows),
                "median_idf_similarity_v0_3": round_float(statistics.median(
                    [float(row["idf_similarity_v0_3"]) for row in rows]
                )),
                "median_same_address_idf_similarity_v0_3": round_float(
                    statistics.median([float(row["idf_similarity_v0_3"]) for row in same_rows])
                    if same_rows else None
                ),
                "axis_a_bucket": SECTION_EXPECTATIONS.get(section_code, {}).get("axis_a_bucket", "unknown_section"),
                "axis_a_eval_role": SECTION_EXPECTATIONS.get(section_code, {}).get("axis_a_eval_role", "excluded"),
                "expected_similarity_rank": SECTION_EXPECTATIONS.get(section_code, {}).get(
                    "expected_similarity_rank", ""
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    eval_fields = [
        "pair_id",
        "section_code",
        "left_object_id",
        "right_object_id",
        "left_subgroup",
        "right_subgroup",
        "left_address_normalized",
        "right_address_normalized",
        "same_address",
        "same_address_cross_system",
        "address_consistency_status",
        "ground_truth_risk",
        "tei_distance_z",
        "tei_distance_field_count",
        "tei_distance_features",
        "tei_bucket",
        "eval_bucket",
        "axis_a_bucket",
        "axis_a_eval_role",
        "expected_similarity_rank",
        "idf_similarity_v0_3",
        "combined_similarity_v0_2",
        "section_percentile_v0_3",
        "page_signature_idf_jaccard",
    ]
    write_csv(output_dir / "eval_pair_labels_v0.csv", eval_rows, eval_fields)
    write_csv(output_dir / "same_address_section_gradient_v0.csv", same_address_rows, eval_fields)
    write_csv(
        output_dir / "eval_section_summary_v0.csv",
        section_summary_rows,
        [
            "section_code",
            "pair_count",
            "same_address_cross_system_count",
            "median_idf_similarity_v0_3",
            "median_same_address_idf_similarity_v0_3",
            "axis_a_bucket",
            "axis_a_eval_role",
            "expected_similarity_rank",
        ],
    )

    summary = {
        "schema_version": "eval_set_v0",
        "generated_at": generated_at,
        "object_registry_path": str(object_registry_path),
        "address_consistency_path": str(address_consistency_path),
        "comparison_v0_3_path": str(comparison_v0_3_path),
        "output_dir": str(output_dir),
        "pair_count": len(eval_rows),
        "same_address_cross_system_count": len(same_address_rows),
        "eval_bucket_counts": dict(sorted(bucket_counter.items())),
        "same_address_consistency_counts": dict(sorted(consistency_counter.items())),
        "tei_features": TEI_FEATURES,
        "tei_stats": {
            feature: {
                "mean": round_float(values["mean"]),
                "stdev": round_float(values["stdev"]),
                "count": values["count"],
            }
            for feature, values in tei_stats.items()
        },
        "tei_distance_thresholds": {
            "near_q25": round_float(near_threshold),
            "far_q75": round_float(far_threshold),
            "basis": "non-same-address unique object pairs only; TEI z-score distance",
        },
        "axis_a_same_address_primary": {
            "row_count": len(primary_axis_a),
            "spearman_expected_vs_idf": round_float(spearman(axis_a_expected, axis_a_observed)),
            "spearman_expected_vs_section_percentile": round_float(spearman(axis_a_expected, axis_a_percentile)),
            "note": "Domain-anchored section gradient; excludes diagnostic sections and TEI-inconsistent same-address rows.",
        },
        "axis_b_tei_distance": {
            "row_count": len(non_same_rows),
            "spearman_distance_vs_idf": round_float(spearman(axis_b_distance, axis_b_similarity)),
            "spearman_distance_vs_v0_2": round_float(spearman(axis_b_distance, axis_b_baseline)),
            "note": "Exploratory size/TEI axis; rank relation, not a fitted threshold.",
        },
        "modeling_rules": [
            "Eval validates mechanism; it is not a fitting target.",
            "TEI/domain fields stay outside core scoring.",
            "Axis A uses idf similarity for content/system differences.",
            "Axis B uses TEI distance and absolute/count gradients, not jaccard alone.",
            "Pre-expertise TEI-inconsistent same-address pairs are flagged as ground-truth risk.",
        ],
        "files": {
            "eval_pair_labels": "eval_pair_labels_v0.csv",
            "same_address_section_gradient": "same_address_section_gradient_v0.csv",
            "eval_section_summary": "eval_section_summary_v0.csv",
        },
    }
    write_json(output_dir / "eval_set_v0.json", summary)

    readme = f"""# eval_set_v0

Eval scaffolding for DocSpectrum pairwise DF/IDF validation.

Generated at:

- `{generated_at}`

Inputs:

- object registry: `{object_registry_path}`
- address TEI consistency: `{address_consistency_path}`
- pairwise v0.3: `{comparison_v0_3_path}`

Key policy:

- This layer validates behavior; it does not tune scoring.
- TEI/domain fields are eval context only and do not enter core scoring.
- Axis A is content/system similarity.
- Axis B is size/TEI distance.
- Same-address TEI-inconsistent pairs are flagged as ground-truth risk.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--object-registry",
        default=r"E:\output\DocSpectrum\object_registry_v0\object_registry_v0.csv",
        help="Object registry CSV with normalized TEI fields.",
    )
    parser.add_argument(
        "--address-consistency",
        default=r"E:\output\DocSpectrum\object_registry_v0\address_tei_consistency_v0.csv",
        help="Address-level TEI consistency CSV.",
    )
    parser.add_argument(
        "--comparison-v0-3",
        default=r"E:\output\DocSpectrum\comparison_results_v0_3_18_n2\comparison_results_v0_3.csv",
        help="Pairwise comparison v0.3 CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\output\DocSpectrum\eval_set_v0_18_n2",
        help="Directory for eval-set artifacts.",
    )
    args = parser.parse_args()
    build(
        Path(args.object_registry),
        Path(args.address_consistency),
        Path(args.comparison_v0_3),
        Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
