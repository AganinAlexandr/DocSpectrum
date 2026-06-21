#!/usr/bin/env python3
"""Validate the corrected remark-depth heuristic against 58 human labels."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from build_expert_quality_experiment_c_v0 import xlsx_rows
from remark_features import feature_row


DEFAULT_LABELS = Path(
    r"E:\commons\DocSpectrum\experiment_c_probes_v0"
    r"\depth_calibration_labeled_v1.xlsx"
)
DEFAULT_FEATURES = Path(
    r"E:\output\DocSpectrum\expert_quality_remark_recall_v0"
    r"\remark_features_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\remark_depth_calibration_v1"
)
REFERENCE_ROLE_MEANS = {
    "class_1": 1.75,
    "floor_3": 1.45,
    "holdout": 1.00,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def role_key(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("ceiling"):
        return "class_1"
    if normalized.startswith("floor"):
        return "floor_3"
    if normalized == "holdout":
        return "holdout"
    return normalized or "unlabeled"


def predicted_level(depth_class: str) -> int:
    return 2 if depth_class == "substantial_candidate" else 1


def normalize_label_text(value: Any) -> str:
    return str(value or "").replace("_x000D_", " ").replace("\r", " ").replace("\n", " ")


def load_labels(path: Path) -> list[dict[str, Any]]:
    rows = xlsx_rows(path, "разметка", 2)
    output = []
    for raw in rows:
        text = normalize_label_text(raw.get(8))
        if not text:
            continue
        features = feature_row(text)
        human_complexity = int(float(str(raw.get(9))))
        human_significance = int(float(str(raw.get(10))))
        output.append(
            {
                "label_id": int(float(str(raw.get(0)))),
                "object_id": str(raw.get(1) or "").strip(),
                "section_code": str(raw.get(2) or "").strip(),
                "role_key": role_key(raw.get(3)),
                "source_label": str(raw.get(5) or "").strip(),
                "human_has_norm_ref": str(raw.get(7) or "").strip().lower() == "да",
                "human_complexity_level": human_complexity,
                "human_significance_level": human_significance,
                "human_category": str(raw.get(11) or "").strip(),
                **features,
                "predicted_complexity_level": predicted_level(features["depth_class_v0"]),
            }
        )
    return output


def summarize(labels: list[dict[str, Any]], feature_hashes: set[str]) -> dict[str, Any]:
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        by_role[row["role_key"]].append(row)

    role_rows = []
    for role, rows in sorted(by_role.items()):
        human = [int(row["human_complexity_level"]) for row in rows]
        predicted = [int(row["predicted_complexity_level"]) for row in rows]
        role_rows.append(
            {
                "role_key": role,
                "label_count": len(rows),
                "human_complexity_mean": round(mean(human), 4),
                "predicted_complexity_mean": round(mean(predicted), 4),
                "exact_agreement_share": round(
                    sum(a == b for a, b in zip(human, predicted)) / len(rows), 4
                ),
                "human_level_1_count": sum(value == 1 for value in human),
                "human_level_2_count": sum(value == 2 for value in human),
                "human_level_3_count": sum(value == 3 for value in human),
            }
        )

    confusion = Counter(
        (int(row["human_complexity_level"]), int(row["predicted_complexity_level"]))
        for row in labels
    )
    confusion_rows = [
        {
            "human_complexity_level": key[0],
            "predicted_complexity_level": key[1],
            "count": count,
        }
        for key, count in sorted(confusion.items())
    ]
    exact = sum(
        int(row["human_complexity_level"]) == int(row["predicted_complexity_level"])
        for row in labels
    )
    norm = [row for row in labels if row["human_has_norm_ref"]]
    no_norm = [row for row in labels if not row["human_has_norm_ref"]]
    true_positive = confusion[(2, 2)]
    false_positive = confusion[(1, 2)]
    false_negative = confusion[(2, 1)]
    level_2_precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    level_2_recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )

    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in labels:
        by_hash[row["remark_hash"]].append(row)
    unanimous_hashes = {
        remark_hash: rows
        for remark_hash, rows in by_hash.items()
        if len({int(row["human_complexity_level"]) for row in rows}) == 1
    }
    unique_hash_exact = sum(
        int(rows[0]["human_complexity_level"])
        == int(rows[0]["predicted_complexity_level"])
        for rows in unanimous_hashes.values()
    )
    return {
        "role_rows": role_rows,
        "confusion_rows": confusion_rows,
        "headline": {
            "label_count": len(labels),
            "unique_remark_hash_count": len({row["remark_hash"] for row in labels}),
            "feature_hash_match_count": sum(
                row["remark_hash"] in feature_hashes for row in labels
            ),
            "exact_agreement_count": exact,
            "exact_agreement_share": round(exact / len(labels), 4),
            "level_2_precision": round(level_2_precision, 4),
            "level_2_recall": round(level_2_recall, 4),
            "unique_hash_unanimous_count": len(unanimous_hashes),
            "unique_hash_conflicting_label_count": len(by_hash) - len(unanimous_hashes),
            "unique_hash_exact_agreement_share": round(
                unique_hash_exact / len(unanimous_hashes), 4
            ),
            "human_level_3_count": sum(
                int(row["human_complexity_level"]) == 3 for row in labels
            ),
            "human_complexity_mean_with_norm": round(
                mean(int(row["human_complexity_level"]) for row in norm), 4
            ),
            "human_complexity_mean_without_norm": round(
                mean(int(row["human_complexity_level"]) for row in no_norm), 4
            ),
            "human_significance_mean": round(
                mean(int(row["human_significance_level"]) for row in labels), 4
            ),
        },
    }


def build(
    labels_path: Path,
    features_path: Path,
    output_dir: Path,
    assert_reference: bool = False,
) -> dict[str, Any]:
    labels = load_labels(labels_path)
    features = read_csv(features_path)
    feature_hashes = {row["remark_hash"] for row in features}
    result = summarize(labels, feature_hashes)
    role_means = {
        row["role_key"]: row["human_complexity_mean"]
        for row in result["role_rows"]
    }
    reference_check = {
        role: {
            "expected": expected,
            "actual": role_means.get(role),
            "status": (
                "matched"
                if abs(float(role_means.get(role, -999)) - expected) < 0.01
                else "changed"
            ),
        }
        for role, expected in REFERENCE_ROLE_MEANS.items()
    }
    if assert_reference:
        changed = {
            role: row for role, row in reference_check.items()
            if row["status"] != "matched"
        }
        if changed or len(labels) != 58:
            raise ValueError(
                f"Depth calibration reference changed: labels={len(labels)}, {changed}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    label_fields = [
        "label_id",
        "object_id",
        "section_code",
        "role_key",
        "source_label",
        "human_has_norm_ref",
        "human_complexity_level",
        "human_significance_level",
        "human_category",
        "remark_hash",
        "char_count",
        "word_count",
        "primary_category_v0",
        "categories_v0",
        "depth_class_v0",
        "depth_reason_codes_v0",
        "predicted_complexity_level",
    ]
    write_csv(output_dir / "remark_depth_labels_hash_only_v1.csv", labels, label_fields)
    write_csv(
        output_dir / "remark_depth_calibration_by_role_v1.csv",
        result["role_rows"],
        list(result["role_rows"][0]),
    )
    write_csv(
        output_dir / "remark_depth_confusion_v1.csv",
        result["confusion_rows"],
        ["human_complexity_level", "predicted_complexity_level", "count"],
    )
    summary = {
        "schema_version": "remark_depth_calibration_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "headline": result["headline"],
        "reference_check": reference_check,
        "interpretation": {
            "human_labels": "ground_truth_on_labeled_subset",
            "heuristic": "triage_only_not_final_quality_output",
            "final_depth_recommendation": "human_labels_plus_count_recall",
            "norm_citation": "removed_as_substantial_signal",
            "level_3": "not_observed_in_current_capital_repair_sample",
            "significance": "separate_flat_axis_not_primary_discriminator",
        },
    }
    (output_dir / "remark_depth_calibration_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate remark-depth heuristic.")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--assert-reference", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build(args.labels, args.features, args.output_dir, args.assert_reference)
    print(json.dumps(summary["headline"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
