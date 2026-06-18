#!/usr/bin/env python3
"""Build provenance-first assessments and a stratified pending review sample."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_QUEUE = Path(
    r"E:\output\DocSpectrum\page_near_match_triage_v0\page_near_match_triage_queue_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\provenance_assessment_v0")

LABEL_TO_PROVENANCE = {
    "normative_form": {
        "authorship_scope": "third_party",
        "source_class": "external_form",
        "source_subclass": "manufacturer_or_regulatory_form",
        "distinctiveness_class": "shared_standard",
        "borrowing_eligibility": "ineligible_third_party",
        "borrowing_signal_status": "confirmed_non_copy",
        "reason_code": "PROVENANCE_THIRD_PARTY_FORM",
    },
    "estimate_boilerplate": {
        "authorship_scope": "third_party",
        "source_class": "software_generated",
        "source_subclass": "estimate_software_output",
        "distinctiveness_class": "shared_standard",
        "borrowing_eligibility": "ineligible_third_party",
        "borrowing_signal_status": "confirmed_non_copy",
        "reason_code": "PROVENANCE_SOFTWARE_GENERATED",
    },
    "shared_technical_content": {
        "authorship_scope": "third_party",
        "source_class": "vendor_technical_material",
        "source_subclass": "equipment_product_documentation",
        "distinctiveness_class": "shared_technical",
        "borrowing_eligibility": "ineligible_third_party",
        "borrowing_signal_status": "confirmed_non_copy",
        "reason_code": "PROVENANCE_VENDOR_TECHNICAL",
    },
    "borrowing_candidate": {
        "authorship_scope": "organization_authored",
        "source_class": "project_content",
        "source_subclass": "org_authored_distinctive",
        "distinctiveness_class": "distinctive",
        "borrowing_eligibility": "eligible_for_review",
        "borrowing_signal_status": "research_candidate",
        "reason_code": "PROVENANCE_ORG_AUTHORED_DISTINCTIVE",
    },
    "false_positive": {
        "authorship_scope": "none",
        "source_class": "no_material_match",
        "source_subclass": "near_match_false_positive",
        "distinctiveness_class": "no_match",
        "borrowing_eligibility": "ineligible_no_match",
        "borrowing_signal_status": "confirmed_non_copy",
        "reason_code": "PROVENANCE_NO_MATERIAL_MATCH",
    },
    "uncertain": {
        "authorship_scope": "unresolved",
        "source_class": "unresolved",
        "source_subclass": "expert_uncertain",
        "distinctiveness_class": "unknown",
        "borrowing_eligibility": "blocked_unresolved",
        "borrowing_signal_status": "not_assessable",
        "reason_code": "PROVENANCE_UNRESOLVED",
    },
}
UNASSESSED = {
    "authorship_scope": "unknown",
    "source_class": "unassessed",
    "source_subclass": "pending_expert_review",
    "distinctiveness_class": "unknown",
    "borrowing_eligibility": "blocked_unassessed",
    "borrowing_signal_status": "not_assessable",
    "reason_code": "PROVENANCE_NOT_ASSESSED",
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


def number(row: dict[str, str], field: str) -> float:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError):
        return 0.0


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def overlap_band(value: float, q1: float, q2: float) -> str:
    if value <= q1:
        return "low"
    if value <= q2:
        return "middle"
    return "high"


def assess_row(row: dict[str, str]) -> dict[str, Any]:
    label = row.get("review_label", "")
    provenance = LABEL_TO_PROVENANCE.get(label, UNASSESSED)
    return {
        **row,
        "provenance_status": "expert_assessed" if label else "unassessed",
        **provenance,
        "provenance_confidence": row.get("review_confidence", "") if label else "",
        "provenance_evidence_type": "human_expert_review" if label else "none",
        "provenance_evidence_ref": (
            f"page_near_match_triage_labels_v0.csv#{row['candidate_id']}"
            if label
            else ""
        ),
        "org_authored_residual_status": (
            "excluded_third_party"
            if provenance["authorship_scope"] == "third_party"
            else "candidate_org_authored"
            if provenance["authorship_scope"] == "organization_authored"
            else "not_available"
        ),
    }


def stratified_sample(
    pending_rows: list[dict[str, Any]],
    per_stratum: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pending_rows:
        by_section[row["left_section_code"]].append(row)

    enriched: list[dict[str, Any]] = []
    thresholds: dict[str, Any] = {}
    for section, rows in sorted(by_section.items()):
        text_values = [number(row, "text_segment_jaccard") for row in rows]
        ratio_values = [
            number(row, "near_match_similarity_v0")
            / max(number(row, "text_segment_jaccard"), 1e-9)
            for row in rows
        ]
        q1 = quantile(text_values, 1 / 3)
        q2 = quantile(text_values, 2 / 3)
        ratio_median = median(ratio_values)
        thresholds[section] = {
            "text_jaccard_q33": round(q1, 4),
            "text_jaccard_q67": round(q2, 4),
            "structure_text_ratio_median": round(ratio_median, 4),
        }
        for row, ratio in zip(rows, ratio_values):
            enriched.append(
                {
                    **row,
                    "sample_section": section,
                    "sample_overlap_band": overlap_band(
                        number(row, "text_segment_jaccard"),
                        q1,
                        q2,
                    ),
                    "sample_structure_text_ratio": round(ratio, 4),
                    "sample_ratio_band": (
                        "structure_dominant"
                        if ratio > ratio_median
                        else "text_stronger"
                    ),
                }
            )

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        key = (
            row["sample_section"],
            row["sample_overlap_band"],
            row["sample_ratio_band"],
        )
        groups[key].append(row)

    selected: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        rows.sort(
            key=lambda row: (
                abs(number(row, "near_match_similarity_v0") - 0.9),
                row["candidate_id"],
            )
        )
        for row in rows[:per_stratum]:
            selected.append(
                {
                    **row,
                    "sample_stratum": "|".join(key),
                    "sample_selection_reason": (
                        "section_x_text_overlap_band_x_structure_text_ratio"
                    ),
                }
            )
    selected.sort(
        key=lambda row: (
            row["sample_section"],
            row["sample_overlap_band"],
            row["sample_ratio_band"],
            row["candidate_id"],
        )
    )
    for index, row in enumerate(selected, start=1):
        row["sample_rank"] = index
    return selected, thresholds


def build(
    queue_path: Path,
    output_dir: Path,
    per_stratum: int,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    queue = read_csv(queue_path)
    assessed = [assess_row(row) for row in queue]
    pending = [row for row in assessed if row["provenance_status"] == "unassessed"]
    sample, thresholds = stratified_sample(pending, per_stratum)

    assessment_fields = list(assessed[0])
    sample_fields = [
        "sample_rank",
        "sample_stratum",
        "sample_section",
        "sample_overlap_band",
        "sample_ratio_band",
        "sample_structure_text_ratio",
        "sample_selection_reason",
    ] + assessment_fields
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "page_provenance_assessment_v0.csv",
        assessed,
        assessment_fields,
    )
    write_csv(
        output_dir / "page_provenance_review_sample_v0.csv",
        sample,
        sample_fields,
    )

    summary = {
        "schema_version": "provenance_assessment_v0",
        "generated_at": generated_at,
        "candidate_count": len(assessed),
        "provenance_status_counts": dict(
            sorted(Counter(row["provenance_status"] for row in assessed).items())
        ),
        "authorship_scope_counts": dict(
            sorted(Counter(row["authorship_scope"] for row in assessed).items())
        ),
        "source_class_counts": dict(
            sorted(Counter(row["source_class"] for row in assessed).items())
        ),
        "borrowing_eligibility_counts": dict(
            sorted(Counter(row["borrowing_eligibility"] for row in assessed).items())
        ),
        "borrowing_signal_status_counts": dict(
            sorted(
                Counter(row["borrowing_signal_status"] for row in assessed).items()
            )
        ),
        "stratified_sample_count": len(sample),
        "sample_stratum_counts": dict(
            sorted(Counter(row["sample_stratum"] for row in sample).items())
        ),
        "sample_thresholds": thresholds,
        "rules": [
            "provenance is assessed before borrowing interpretation.",
            "unassessed provenance blocks borrowing eligibility.",
            "third-party authored material is excluded from organization handwriting residuals.",
            "borrowing_candidate requires expert-supported organization-authored distinctive content.",
            "the review sample is stratified and is not selected by top score.",
        ],
        "files": {
            "assessment": "page_provenance_assessment_v0.csv",
            "review_sample": "page_provenance_review_sample_v0.csv",
        },
    }
    (output_dir / "provenance_assessment_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build provenance-first page assessments and review sample."
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--per-stratum", type=int, default=2)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.queue, args.output_dir, args.per_stratum),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
