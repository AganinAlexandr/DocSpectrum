#!/usr/bin/env python3
"""Assess expanded H2 cells and replication against the original corpus."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_OLD = Path(
    r"E:\output\DocSpectrum\gip_control_h2_alias_canon_v0"
    r"\gip_control_h2_cells_v0.csv"
)
DEFAULT_EXPANDED = Path(
    r"E:\output\DocSpectrum\gip_control_h2_alias_canon_expanded_v0"
    r"\gip_control_h2_cells_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\gip_control_h2_expansion_v0"
)


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
    value = row.get(field, "")
    return float(value) if value not in ("", None) else 0.0


def classify_channel(retentions: list[float]) -> str:
    strong = sum(value >= 0.75 for value in retentions)
    weak = sum(value >= 0.40 for value in retentions)
    if strong == len(retentions):
        return "transfer"
    if strong >= 1 or weak == len(retentions):
        return "partial"
    return "org_bound"


def assess_cell(row: dict[str, str]) -> dict[str, Any]:
    same_count = int(row["same_org_pair_count"])
    cross_count = int(row["cross_org_pair_count"])
    sufficient = same_count >= 3 and cross_count >= 3
    structural_values = [
        number(row, "cross_to_same_style_composition_ratio"),
        number(row, "cross_to_same_near_structural_ratio"),
    ]
    content_values = [
        number(row, "cross_to_same_residual_shingle_ratio"),
        number(row, "cross_to_same_residual_strong_share_ratio"),
    ]
    structural = classify_channel(structural_values)
    content = classify_channel(content_values)
    if not sufficient:
        overall = "insufficient"
    elif structural == "transfer" and content == "transfer":
        overall = "transfer_both"
    elif structural == "transfer" and content != "transfer":
        overall = "structure_led"
    elif content == "transfer" and structural != "transfer":
        overall = "content_led"
    elif structural == "org_bound" and content == "org_bound":
        overall = "org_bound"
    else:
        overall = "mixed_partial"
    return {
        **row,
        "minimum_pair_support_met": sufficient,
        "structural_transfer_status": structural,
        "content_transfer_status": content,
        "h2_transfer_status": overall,
    }


def cell_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["gip"], row["work_type_key"], row["section_code"]


def build(old_path: Path, expanded_path: Path, output_dir: Path) -> dict[str, Any]:
    old_rows = {
        cell_key(row): assess_cell(row)
        for row in read_csv(old_path)
        if row["comparison_status"] == "matched_same_and_cross"
    }
    expanded = [
        assess_cell(row)
        for row in read_csv(expanded_path)
        if row["comparison_status"] == "matched_same_and_cross"
    ]

    replication_rows = []
    for row in expanded:
        old = old_rows.get(cell_key(row))
        if old is None:
            replication = "new_cell"
        elif row["h2_transfer_status"] == old["h2_transfer_status"]:
            replication = "status_persisted"
        elif "insufficient" in {
            row["h2_transfer_status"],
            old["h2_transfer_status"],
        }:
            replication = "support_changed"
        else:
            replication = "status_changed"
        replication_rows.append(
            {
                "gip": row["gip"],
                "work_type_key": row["work_type_key"],
                "section_code": row["section_code"],
                "replication_status": replication,
                "old_same_org_pair_count": old["same_org_pair_count"] if old else "",
                "old_cross_org_pair_count": old["cross_org_pair_count"] if old else "",
                "old_h2_transfer_status": old["h2_transfer_status"] if old else "",
                "expanded_same_org_pair_count": row["same_org_pair_count"],
                "expanded_cross_org_pair_count": row["cross_org_pair_count"],
                "expanded_h2_transfer_status": row["h2_transfer_status"],
            }
        )

    by_gip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in expanded:
        by_gip[row["gip"]].append(row)
    gip_rows = []
    for gip, rows in sorted(by_gip.items()):
        supported = [row for row in rows if row["minimum_pair_support_met"]]
        statuses = Counter(row["h2_transfer_status"] for row in supported)
        structural_retention = [
            number(row, "cross_to_same_style_composition_ratio")
            for row in supported
        ]
        content_retention = [
            number(row, "cross_to_same_residual_strong_share_ratio")
            for row in supported
        ]
        content_statuses = Counter(
            row["content_transfer_status"] for row in supported
        )
        structural_statuses = Counter(
            row["structural_transfer_status"] for row in supported
        )
        if statuses["transfer_both"] >= max(1, len(supported) / 2):
            headline = "transfer_supported"
        elif supported and content_statuses["org_bound"] == len(supported):
            headline = "content_org_bound_structural_residue"
        elif supported and structural_statuses["transfer"] == len(supported):
            headline = "structure_transfer_content_mixed"
        elif supported:
            headline = "mixed_by_section"
        else:
            headline = "insufficient"
        if len(supported) == 1:
            headline += "_preliminary"
        gip_rows.append(
            {
                "gip": gip,
                "matched_cell_count": len(rows),
                "supported_cell_count": len(supported),
                "insufficient_cell_count": len(rows) - len(supported),
                "headline_status": headline,
                "cell_status_counts": "|".join(
                    f"{key}:{value}" for key, value in sorted(statuses.items())
                ),
                "style_composition_retention_median": round(
                    median(structural_retention), 4
                )
                if structural_retention
                else "",
                "strong_share_retention_median": round(
                    median(content_retention), 4
                )
                if content_retention
                else "",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    cell_fields = list(expanded[0])
    write_csv(output_dir / "gip_control_h2_cell_assessment_v0.csv", expanded, cell_fields)
    replication_fields = list(replication_rows[0])
    write_csv(
        output_dir / "gip_control_h2_replication_v0.csv",
        replication_rows,
        replication_fields,
    )
    gip_fields = list(gip_rows[0])
    write_csv(output_dir / "gip_control_h2_gip_assessment_v0.csv", gip_rows, gip_fields)

    replication_counts = Counter(
        row["replication_status"] for row in replication_rows
    )
    summary = {
        "schema_version": "gip_control_h2_expansion_v0",
        "old_matched_cell_count": len(old_rows),
        "expanded_matched_cell_count": len(expanded),
        "supported_expanded_cell_count": sum(
            row["minimum_pair_support_met"] for row in expanded
        ),
        "replication_status_counts": dict(sorted(replication_counts.items())),
        "gip_headlines": {
            row["gip"]: row["headline_status"] for row in gip_rows
        },
        "thresholds": {
            "minimum_same_org_pairs": 3,
            "minimum_cross_org_pairs": 3,
            "channel_transfer_retention": 0.75,
            "channel_partial_retention": 0.40,
        },
    }
    (output_dir / "gip_control_h2_expansion_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess expanded H2 evidence.")
    parser.add_argument("--old", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--expanded", type=Path, default=DEFAULT_EXPANDED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.old, args.expanded, args.output_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
