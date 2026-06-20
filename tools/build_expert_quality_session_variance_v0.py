#!/usr/bin/env python3
"""Aggregate experiment C outcomes at the expert-session level.

A session is one expert x organization x work-type x start-date batch. KR and
POS reviewed in the same batch remain one observation; object rows inside the
batch are correlated evidence, not independent quality observations.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pvariance
from typing import Any


DEFAULT_REGISTRY_ROWS = Path(
    r"E:\output\DocSpectrum\expert_quality_experiment_c_v0"
    r"\expert_quality_registry_rows_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\expert_quality_session_variance_v0"
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


def as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def merge_object_section_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Collapse duplicate registry lines without inventing independent evidence."""
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("expert_hash", ""),
            row.get("organization", ""),
            row.get("work_type", ""),
            row.get("session_start_date", ""),
            row.get("object_id", ""),
            row.get("section_code", ""),
        )
        grouped[key].append(row)

    output = []
    for key, members in sorted(grouped.items()):
        roles = sorted(
            {
                row.get("expert_anchor_role", "")
                for row in members
                if row.get("expert_anchor_role", "")
            }
        )
        classes = sorted(
            {
                row.get("expert_quality_class", "")
                for row in members
                if row.get("expert_quality_class", "")
            }
        )
        output.append(
            {
                "expert_hash": key[0],
                "organization": key[1],
                "work_type": key[2],
                "session_start_date": key[3],
                "object_id": key[4],
                "section_code": key[5],
                "expert_anchor_role": "|".join(roles),
                "expert_quality_class": "|".join(classes),
                "has_first_round_remark": any(
                    as_bool(row.get("has_first_round_remark")) for row in members
                ),
                "clean_first_round_pass": any(
                    as_bool(row.get("clean_first_round_pass")) for row in members
                ),
                "source_row_count": len(members),
            }
        )
    return output


def session_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["expert_hash"]),
        str(row["organization"]),
        str(row["work_type"]),
        str(row["session_start_date"]),
    )


def build_session_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        if not row["expert_hash"] or not row["session_start_date"]:
            continue
        if row["section_code"] not in {"КР", "ПОС"}:
            continue
        grouped[session_key(row)].append(row)

    sessions = []
    for key, members in sorted(grouped.items()):
        outcome_known = [
            row
            for row in members
            if row["clean_first_round_pass"] or row["has_first_round_remark"]
        ]
        clean_count = sum(bool(row["clean_first_round_pass"]) for row in members)
        remark_count = sum(bool(row["has_first_round_remark"]) for row in members)
        unresolved_count = len(members) - len(outcome_known)
        roles = sorted(
            {
                str(row["expert_anchor_role"])
                for row in members
                if row["expert_anchor_role"]
            }
        )
        quality_classes = sorted(
            {
                str(row["expert_quality_class"])
                for row in members
                if row["expert_quality_class"]
            }
        )
        objects = {str(row["object_id"]) for row in members}
        sections = {str(row["section_code"]) for row in members}
        denominator = len(members)
        classified = len(outcome_known)
        sessions.append(
            {
                "session_id": "|".join(key),
                "expert_hash": key[0],
                "expert_anchor_role": "|".join(roles),
                "expert_quality_class": "|".join(quality_classes),
                "organization": key[1],
                "work_type": key[2],
                "session_start_date": key[3],
                "object_count": len(objects),
                "section_count": len(members),
                "section_codes": "|".join(sorted(sections)),
                "clean_pass_count": clean_count,
                "remark_count": remark_count,
                "unresolved_outcome_count": unresolved_count,
                "classified_outcome_count": classified,
                "classified_outcome_share": round_float(classified / denominator),
                "clean_share_all_sections": round_float(clean_count / denominator),
                "remark_share_all_sections": round_float(remark_count / denominator),
                "clean_share_classified": (
                    round_float(clean_count / classified) if classified else ""
                ),
                "remark_share_classified": (
                    round_float(remark_count / classified) if classified else ""
                ),
                "session_size_class": (
                    "multi_object_batch" if len(objects) > 1 else "single_object_session"
                ),
            }
        )
    return sessions


def summarize_experts(session_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in session_rows:
        grouped[str(row["expert_hash"])].append(row)

    output = []
    for expert_hash, rows in sorted(grouped.items()):
        clean = [float(row["clean_share_all_sections"]) for row in rows]
        remark = [float(row["remark_share_all_sections"]) for row in rows]
        multi_object_clean = [
            float(row["clean_share_all_sections"])
            for row in rows
            if row["session_size_class"] == "multi_object_batch"
        ]
        classified_multi_object = [
            row
            for row in rows
            if row["session_size_class"] == "multi_object_batch"
            and int(row["classified_outcome_count"]) > 0
        ]
        thorough_sessions = sum(
            float(row["clean_share_classified"]) == 0.0
            for row in classified_multi_object
        )
        skim_sessions = sum(
            float(row["clean_share_classified"]) == 1.0
            for row in classified_multi_object
        )
        mixed_sessions = len(classified_multi_object) - thorough_sessions - skim_sessions
        polarization_denominator = len(classified_multi_object)
        classified_clean = [
            float(row["clean_share_classified"])
            for row in rows
            if row["clean_share_classified"] != ""
        ]
        outcome_coverage = [float(row["classified_outcome_share"]) for row in rows]
        roles = sorted(
            {
                str(row["expert_anchor_role"])
                for row in rows
                if row["expert_anchor_role"]
            }
        )
        classes = sorted(
            {
                str(row["expert_quality_class"])
                for row in rows
                if row["expert_quality_class"]
            }
        )
        total_sections = sum(int(row["section_count"]) for row in rows)
        total_clean = sum(int(row["clean_pass_count"]) for row in rows)
        total_remark = sum(int(row["remark_count"]) for row in rows)
        output.append(
            {
                "expert_hash": expert_hash,
                "expert_anchor_role": "|".join(roles),
                "expert_quality_class": "|".join(classes),
                "session_count": len(rows),
                "multi_object_session_count": sum(
                    row["session_size_class"] == "multi_object_batch" for row in rows
                ),
                "multi_object_session_clean_share_mean": (
                    round_float(mean(multi_object_clean)) if multi_object_clean else ""
                ),
                "multi_object_session_clean_share_variance": (
                    round_float(pvariance(multi_object_clean))
                    if multi_object_clean
                    else ""
                ),
                "multi_object_session_clean_share_range": (
                    round_float(max(multi_object_clean) - min(multi_object_clean))
                    if multi_object_clean
                    else ""
                ),
                "classified_multi_object_session_count": polarization_denominator,
                "thorough_session_count": thorough_sessions,
                "mixed_session_count": mixed_sessions,
                "skim_session_count": skim_sessions,
                "thorough_session_share": (
                    round_float(thorough_sessions / polarization_denominator)
                    if polarization_denominator
                    else ""
                ),
                "mixed_session_share": (
                    round_float(mixed_sessions / polarization_denominator)
                    if polarization_denominator
                    else ""
                ),
                "skim_session_share": (
                    round_float(skim_sessions / polarization_denominator)
                    if polarization_denominator
                    else ""
                ),
                "polarized_session_share": (
                    round_float(
                        (thorough_sessions + skim_sessions) / polarization_denominator
                    )
                    if polarization_denominator
                    else ""
                ),
                "organization_count": len({str(row["organization"]) for row in rows}),
                "work_type_count": len({str(row["work_type"]) for row in rows}),
                "session_clean_share_mean": round_float(mean(clean)),
                "session_clean_share_median": round_float(median(clean)),
                "session_clean_share_variance": round_float(pvariance(clean)),
                "session_clean_share_stddev": round_float(math.sqrt(pvariance(clean))),
                "session_clean_share_min": round_float(min(clean)),
                "session_clean_share_p10": round_float(quantile(clean, 0.10)),
                "session_clean_share_p90": round_float(quantile(clean, 0.90)),
                "session_clean_share_max": round_float(max(clean)),
                "session_clean_share_range": round_float(max(clean) - min(clean)),
                "low_clean_session_share_le_0_25": round_float(
                    sum(value <= 0.25 for value in clean) / len(clean)
                ),
                "high_clean_session_share_ge_0_75": round_float(
                    sum(value >= 0.75 for value in clean) / len(clean)
                ),
                "session_remark_share_variance": round_float(pvariance(remark)),
                "classified_session_count": len(classified_clean),
                "classified_outcome_share_mean": round_float(mean(outcome_coverage)),
                "classified_session_clean_share_mean": (
                    round_float(mean(classified_clean)) if classified_clean else ""
                ),
                "classified_session_clean_share_variance": (
                    round_float(pvariance(classified_clean)) if classified_clean else ""
                ),
                "classified_session_clean_share_range": (
                    round_float(max(classified_clean) - min(classified_clean))
                    if classified_clean
                    else ""
                ),
                "weighted_clean_share_all_sections": round_float(
                    total_clean / total_sections if total_sections else 0.0
                ),
                "weighted_remark_share_all_sections": round_float(
                    total_remark / total_sections if total_sections else 0.0
                ),
                "interpretation_status": (
                    "measured_across_sessions"
                    if len(rows) >= 2
                    else "insufficient_single_session"
                ),
            }
        )
    return output


def prime_batch_check(session_rows: list[dict[str, Any]]) -> dict[str, Any]:
    holdout_rows = [
        row
        for row in session_rows
        if row["expert_anchor_role"] == "holdout"
        and row["organization"] == "АО ССУ № 3"
        and row["work_type"] == "фундамент"
    ]
    ceiling_rows = [
        row
        for row in session_rows
        if row["expert_anchor_role"] == "ceiling_1_b"
        and row["organization"] == "АО ССУ № 3"
        and row["work_type"] == "фундамент"
    ]
    feb_holdout = next(
        (row for row in holdout_rows if row["session_start_date"] == "2025-02-13"),
        None,
    )
    return {
        "holdout_session_count": len(holdout_rows),
        "ceiling_session_count": len(ceiling_rows),
        "holdout_session_dates": sorted(row["session_start_date"] for row in holdout_rows),
        "ceiling_session_dates": sorted(row["session_start_date"] for row in ceiling_rows),
        "february_holdout_batch": (
            {
                "object_count": feb_holdout["object_count"],
                "section_count": feb_holdout["section_count"],
                "section_codes": feb_holdout["section_codes"],
                "clean_pass_count": feb_holdout["clean_pass_count"],
                "remark_count": feb_holdout["remark_count"],
                "clean_share_all_sections": feb_holdout["clean_share_all_sections"],
                "independent_observation_count": 1,
            }
            if feb_holdout
            else None
        ),
    }


def build(
    registry_rows_path: Path,
    output_dir: Path,
    assert_reference: bool = False,
) -> dict[str, Any]:
    source_rows = read_csv(registry_rows_path)
    records = merge_object_section_rows(source_rows)
    sessions = build_session_rows(records)
    experts = summarize_experts(sessions)
    prime = prime_batch_check(sessions)

    reference = {
        "holdout_session_count": 2,
        "ceiling_session_count": 1,
        "february_holdout_object_count": 10,
        "february_holdout_section_count": 20,
        "february_holdout_clean_pass_count": 20,
        "february_holdout_remark_count": 0,
    }
    actual = {
        "holdout_session_count": prime["holdout_session_count"],
        "ceiling_session_count": prime["ceiling_session_count"],
        "february_holdout_object_count": (
            prime["february_holdout_batch"]["object_count"]
            if prime["february_holdout_batch"]
            else 0
        ),
        "february_holdout_section_count": (
            prime["february_holdout_batch"]["section_count"]
            if prime["february_holdout_batch"]
            else 0
        ),
        "february_holdout_clean_pass_count": (
            prime["february_holdout_batch"]["clean_pass_count"]
            if prime["february_holdout_batch"]
            else 0
        ),
        "february_holdout_remark_count": (
            prime["february_holdout_batch"]["remark_count"]
            if prime["february_holdout_batch"]
            else 0
        ),
    }
    reference_check = {
        key: {
            "expected": expected,
            "actual": actual[key],
            "status": "matched" if actual[key] == expected else "changed",
        }
        for key, expected in reference.items()
    }
    if assert_reference:
        changed = {
            key: value
            for key, value in reference_check.items()
            if value["status"] != "matched"
        }
        if changed:
            raise ValueError(f"Session reference changed: {changed}")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "expert_quality_sessions_v0.csv",
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
        ],
    )
    write_csv(
        output_dir / "expert_quality_session_variance_by_expert_v0.csv",
        experts,
        [
            "expert_hash",
            "expert_anchor_role",
            "expert_quality_class",
            "session_count",
            "multi_object_session_count",
            "multi_object_session_clean_share_mean",
            "multi_object_session_clean_share_variance",
            "multi_object_session_clean_share_range",
            "classified_multi_object_session_count",
            "thorough_session_count",
            "mixed_session_count",
            "skim_session_count",
            "thorough_session_share",
            "mixed_session_share",
            "skim_session_share",
            "polarized_session_share",
            "organization_count",
            "work_type_count",
            "session_clean_share_mean",
            "session_clean_share_median",
            "session_clean_share_variance",
            "session_clean_share_stddev",
            "session_clean_share_min",
            "session_clean_share_p10",
            "session_clean_share_p90",
            "session_clean_share_max",
            "session_clean_share_range",
            "low_clean_session_share_le_0_25",
            "high_clean_session_share_ge_0_75",
            "session_remark_share_variance",
            "classified_session_count",
            "classified_outcome_share_mean",
            "classified_session_clean_share_mean",
            "classified_session_clean_share_variance",
            "classified_session_clean_share_range",
            "weighted_clean_share_all_sections",
            "weighted_remark_share_all_sections",
            "interpretation_status",
        ],
    )
    summary = {
        "schema_version": "expert_quality_session_variance_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(registry_rows_path),
        "session_key": [
            "expert_hash",
            "organization",
            "work_type",
            "session_start_date",
        ],
        "counts": {
            "source_registry_row_count": len(source_rows),
            "collapsed_object_section_record_count": len(records),
            "session_count": len(sessions),
            "expert_count": len(experts),
            "multi_object_session_count": sum(
                row["session_size_class"] == "multi_object_batch" for row in sessions
            ),
        },
        "prime_batch_check": prime,
        "reference_check": reference_check,
        "interpretation": {
            "unit": "expert_x_organization_x_work_type_x_start_date_batch",
            "kr_pos_same_batch": "one_session_with_section_codes_preserved",
            "variance": "descriptive_proxy_until_remark_recall_is_available",
            "quality_class_output": "not_inferred",
            "monthly_load": "not_used_as_session_quality_explanation",
        },
    }
    write_json(output_dir / "expert_quality_session_variance_v0.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build session-level variance artifacts for experiment C."
    )
    parser.add_argument("--registry-rows", type=Path, default=DEFAULT_REGISTRY_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--assert-reference", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build(args.registry_rows, args.output_dir, args.assert_reference)
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
