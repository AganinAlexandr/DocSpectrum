#!/usr/bin/env python3
"""Summarize H2 after organization alias canon on matched comparison cells."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_PAIRWISE = Path(
    r"E:\output\DocSpectrum\gip_control_provenance_residual_v0"
    r"\gip_control_pairwise_provenance_residual_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_control_h2_alias_canon_v0")
H2_KIND = "h2_cross_org_same_gip"
METRICS = {
    "style_composition": "style_composition_similarity_v0",
    "near_structural": "page_near_similarity_mean_v0_2",
    "residual_shingle": "residual_page_near_shingle_mean_v0_3",
    "residual_strong_share": "residual_page_near_strong_share_v0_3",
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


def round_float(value: float | None, digits: int = 4) -> float | str:
    return "" if value is None else round(value, digits)


def metric_median(rows: list[dict[str, str]], field: str) -> float | None:
    values = [value for row in rows if (value := safe_float(row.get(field))) is not None]
    return median(values) if values else None


def relation_metrics(
    same_rows: list[dict[str, str]],
    cross_rows: list[dict[str, str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, field in METRICS.items():
        same_value = metric_median(same_rows, field)
        cross_value = metric_median(cross_rows, field)
        delta = cross_value - same_value if same_value is not None and cross_value is not None else None
        retention = (
            cross_value / same_value
            if same_value not in (None, 0.0) and cross_value is not None
            else None
        )
        result[f"same_org_{label}_median"] = round_float(same_value)
        result[f"cross_org_{label}_median"] = round_float(cross_value)
        result[f"cross_minus_same_{label}"] = round_float(delta)
        result[f"cross_to_same_{label}_ratio"] = round_float(retention)
    return result


def build_cell_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["cell_id"]].append(row)

    result = []
    for cell_id, members in sorted(grouped.items()):
        same_rows = [row for row in members if row["relation"] == "same_org"]
        cross_rows = [row for row in members if row["relation"] == "cross_org"]
        sample = members[0]
        if same_rows and cross_rows:
            status = "matched_same_and_cross"
        elif cross_rows:
            status = "cross_only_no_same_org_baseline"
        else:
            status = "same_only_no_cross_org_test"
        org_pairs = Counter(
            " <> ".join(sorted((row["left_org"], row["right_org"])))
            for row in cross_rows
        )
        result.append(
            {
                "cell_id": cell_id,
                "gip": sample["left_gip"],
                "work_type_key": sample["work_type_key"],
                "section_code": sample["section_code"],
                "comparison_status": status,
                "same_org_pair_count": len(same_rows),
                "cross_org_pair_count": len(cross_rows),
                "cross_org_pairs": "|".join(
                    f"{pair}:{count}" for pair, count in sorted(org_pairs.items())
                ),
                **relation_metrics(same_rows, cross_rows),
            }
        )
    return result


def build_summary_rows(
    pair_rows: list[dict[str, str]],
    cell_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched = [row for row in cell_rows if row["comparison_status"] == "matched_same_and_cross"]
    summary: dict[str, Any] = {
        "scope": "matched_cells_equal_weight",
        "cell_count": len(matched),
        "gip_count": len({row["gip"] for row in matched}),
        "same_org_pair_count": sum(int(row["same_org_pair_count"]) for row in matched),
        "cross_org_pair_count": sum(int(row["cross_org_pair_count"]) for row in matched),
    }
    for label in METRICS:
        same_values = [
            float(row[f"same_org_{label}_median"])
            for row in matched
            if row[f"same_org_{label}_median"] != ""
        ]
        cross_values = [
            float(row[f"cross_org_{label}_median"])
            for row in matched
            if row[f"cross_org_{label}_median"] != ""
        ]
        delta_values = [
            float(row[f"cross_minus_same_{label}"])
            for row in matched
            if row[f"cross_minus_same_{label}"] != ""
        ]
        summary[f"same_org_{label}_cell_median"] = round_float(
            median(same_values) if same_values else None
        )
        summary[f"cross_org_{label}_cell_median"] = round_float(
            median(cross_values) if cross_values else None
        )
        summary[f"cross_minus_same_{label}_cell_median"] = round_float(
            median(delta_values) if delta_values else None
        )

    same_pairs = [row for row in pair_rows if row["relation"] == "same_org"]
    cross_pairs = [row for row in pair_rows if row["relation"] == "cross_org"]
    pair_weighted = {
        "scope": "all_pairs_pair_weighted_diagnostic",
        "cell_count": len(cell_rows),
        "gip_count": len({row["left_gip"] for row in pair_rows}),
        "same_org_pair_count": len(same_pairs),
        "cross_org_pair_count": len(cross_pairs),
        **relation_metrics(same_pairs, cross_pairs),
    }
    return [summary, pair_weighted]


def build_gip_summary_rows(cell_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cell_rows:
        if row["comparison_status"] == "matched_same_and_cross":
            grouped[row["gip"]].append(row)

    result = []
    for gip, rows in sorted(grouped.items()):
        summary: dict[str, Any] = {
            "gip": gip,
            "matched_cell_count": len(rows),
            "sections": "|".join(sorted({row["section_code"] for row in rows})),
            "work_types": "|".join(sorted({row["work_type_key"] for row in rows})),
            "same_org_pair_count": sum(int(row["same_org_pair_count"]) for row in rows),
            "cross_org_pair_count": sum(int(row["cross_org_pair_count"]) for row in rows),
        }
        for label in METRICS:
            for prefix in ("same_org", "cross_org", "cross_minus_same"):
                field = f"{prefix}_{label}"
                source = f"{field}_median" if prefix != "cross_minus_same" else field
                values = [
                    float(row[source])
                    for row in rows
                    if row[source] != ""
                ]
                summary[f"{field}_cell_median"] = round_float(
                    median(values) if values else None
                )
        result.append(summary)
    return result


def build(pairwise_path: Path, output_dir: Path) -> dict[str, Any]:
    pair_rows = [
        row for row in read_csv(pairwise_path)
        if row.get("cell_kind") == H2_KIND
    ]
    cell_rows = build_cell_rows(pair_rows)
    summary_rows = build_summary_rows(pair_rows, cell_rows)
    gip_summary_rows = build_gip_summary_rows(cell_rows)
    matched_cells = [
        row for row in cell_rows if row["comparison_status"] == "matched_same_and_cross"
    ]
    cross_only_cells = [
        row for row in cell_rows
        if row["comparison_status"] == "cross_only_no_same_org_baseline"
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    cell_fields = list(cell_rows[0]) if cell_rows else []
    summary_fields = list(summary_rows[0]) if summary_rows else []
    for row in summary_rows:
        for field in row:
            if field not in summary_fields:
                summary_fields.append(field)
    write_csv(output_dir / "gip_control_h2_cells_v0.csv", cell_rows, cell_fields)
    write_csv(output_dir / "gip_control_h2_summary_v0.csv", summary_rows, summary_fields)
    write_csv(
        output_dir / "gip_control_h2_gip_summary_v0.csv",
        gip_summary_rows,
        list(gip_summary_rows[0]) if gip_summary_rows else [],
    )
    write_csv(
        output_dir / "gip_control_h2_data_gaps_v0.csv",
        cross_only_cells,
        cell_fields,
    )

    payload = {
        "schema_version": "gip_control_h2_alias_canon_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_pairwise": str(pairwise_path),
        "pair_count": len(pair_rows),
        "same_org_pair_count": sum(row["relation"] == "same_org" for row in pair_rows),
        "cross_org_pair_count": sum(row["relation"] == "cross_org" for row in pair_rows),
        "cell_count": len(cell_rows),
        "matched_cell_count": len(matched_cells),
        "cross_only_cell_count": len(cross_only_cells),
        "matched_gips": sorted({row["gip"] for row in matched_cells}),
        "cross_only_gips": sorted({row["gip"] for row in cross_only_cells}),
        "notes": [
            "Organization labels are already canonicalized by the GIP registry alias layer.",
            "Primary H2 reading uses equal-weight matched cells with both same-org and cross-org pairs.",
            "Pair-weighted all-pairs values are diagnostic because large cells otherwise dominate.",
            "Cross-only cells are data-acquisition targets, not evidence against H2.",
        ],
        "files": {
            "cells": "gip_control_h2_cells_v0.csv",
            "summary": "gip_control_h2_summary_v0.csv",
            "gip_summary": "gip_control_h2_gip_summary_v0.csv",
            "data_gaps": "gip_control_h2_data_gaps_v0.csv",
        },
    }
    write_json(output_dir / "gip_control_h2_alias_canon_v0.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build alias-canonical matched-cell H2 summary.")
    parser.add_argument("--pairwise", type=Path, default=DEFAULT_PAIRWISE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.pairwise, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
