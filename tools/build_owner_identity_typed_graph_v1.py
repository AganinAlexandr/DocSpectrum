#!/usr/bin/env python3
"""Type owner-identity edges without changing the v0 similarity matrix."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MATRIX = Path(
    r"E:\output\DocSpectrum\owner_identity_org_matrix_v0\owner_identity_org_matrix_v0.csv"
)
DEFAULT_OBJECTS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0\gip_control_objects_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\owner_identity_typed_graph_v1")
RENAME_HANDOFF_THRESHOLD = 0.40


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
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
    try:
        if value in ("", None):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def truthy(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def percentile(values: list[int], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def classify_edge(row: dict[str, str]) -> tuple[str, str]:
    handwriting = truthy(row.get("handwriting_candidate_v0"))
    network = safe_int(row.get("four_title_disclosed_object_count")) > 0
    shared_gip = safe_int(row.get("shared_gip_count")) > 0
    handoff = safe_float(row.get("temporal_handoff_score"))

    if network:
        return "disclosed_subcontract_network", "explicit_four_title_evidence"
    if handwriting and shared_gip and handoff >= RENAME_HANDOFF_THRESHOLD:
        return "rename_candidate", "handwriting_shared_gip_temporal_handoff"
    if handwriting and shared_gip:
        return "shared_gip_handwriting", "handwriting_shared_gip_without_rename_handoff"
    if handwriting:
        return "owner_or_template_candidate", "rare_handwriting_without_independent_identity_evidence"
    return "not_in_identity_graph", ""


def connected_components(edges: list[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for left, right in edges:
        graph[left].add(right)
        graph[right].add(left)
    result = []
    seen: set[str] = set()
    for node in sorted(graph):
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(graph[current] - seen):
                seen.add(neighbor)
                stack.append(neighbor)
        result.append(sorted(component))
    return result


def build(matrix_path: Path, objects_path: Path, output_dir: Path) -> dict[str, Any]:
    matrix_rows = read_csv(matrix_path)
    object_rows = read_csv(objects_path)
    object_counts = Counter(
        row["effective_org_canonical"]
        for row in object_rows
        if row.get("effective_org_canonical")
    )
    large_org_threshold = percentile(list(object_counts.values()), 0.90)

    typed_rows: list[dict[str, Any]] = []
    for row in matrix_rows:
        edge_type, basis = classify_edge(row)
        if edge_type == "not_in_identity_graph":
            continue
        left_count = object_counts[row["org_left"]]
        right_count = object_counts[row["org_right"]]
        large_orgs = [
            org
            for org, count in ((row["org_left"], left_count), (row["org_right"], right_count))
            if count >= large_org_threshold
        ]
        typed_rows.append(
            {
                **row,
                "identity_edge_type_v1": edge_type,
                "identity_edge_basis_v1": basis,
                "left_object_count": left_count,
                "right_object_count": right_count,
                "large_org_template_noise_risk": (
                    edge_type == "owner_or_template_candidate" and bool(large_orgs)
                ),
                "large_orgs": "|".join(large_orgs),
                "component_policy_v1": (
                    "core_identity_component"
                    if edge_type in {"rename_candidate", "disclosed_subcontract_network"}
                    else "separate_research_component"
                ),
            }
        )

    components_by_type: dict[str, list[list[str]]] = {}
    component_rows: list[dict[str, Any]] = []
    node_to_core: dict[str, list[str]] = defaultdict(list)
    for edge_type in (
        "rename_candidate",
        "disclosed_subcontract_network",
        "shared_gip_handwriting",
        "owner_or_template_candidate",
    ):
        edges = [
            (row["org_left"], row["org_right"])
            for row in typed_rows
            if row["identity_edge_type_v1"] == edge_type
        ]
        components = connected_components(edges)
        components_by_type[edge_type] = components
        for index, organizations in enumerate(components, 1):
            component_id = f"{edge_type}_{index:03d}"
            component_rows.append(
                {
                    "component_id": component_id,
                    "component_type": edge_type,
                    "organization_count": len(organizations),
                    "organizations": "|".join(organizations),
                    "interpretation": (
                        "library_relative_typed_candidate_not_owner_verdict"
                    ),
                }
            )
            if edge_type in {"rename_candidate", "disclosed_subcontract_network"}:
                for organization in organizations:
                    node_to_core[organization].append(component_id)

    attachment_rows: list[dict[str, Any]] = []
    for row in typed_rows:
        if row["identity_edge_type_v1"] not in {
            "owner_or_template_candidate",
            "shared_gip_handwriting",
        }:
            continue
        left_core = node_to_core.get(row["org_left"], [])
        right_core = node_to_core.get(row["org_right"], [])
        if not left_core and not right_core:
            continue
        if left_core and right_core and set(left_core) == set(right_core):
            status = "secondary_support_inside_core"
        else:
            status = "unvalidated_attachment_to_core"
        attachment_rows.append(
            {
                "org_left": row["org_left"],
                "org_right": row["org_right"],
                "attachment_status": status,
                "edge_type": row["identity_edge_type_v1"],
                "left_core_components": "|".join(left_core),
                "right_core_components": "|".join(right_core),
                "large_org_template_noise_risk": row["large_org_template_noise_risk"],
                "large_orgs": row["large_orgs"],
                "residual_shingle_absolute_median": row["residual_shingle_absolute_median"],
                "residual_strong_share_absolute_median": row[
                    "residual_strong_share_absolute_median"
                ],
                "shared_gips": row["shared_gips"],
            }
        )

    anchors = [
        ("rename_confirmed", "Комтех", "АО ССУ № 3"),
        ("owner_pair_known", "Тиволион", "ООО К1"),
        ("disclosed_subcontract_network", "Ватага", "Спектр"),
    ]
    typed_lookup = {
        tuple(sorted((row["org_left"], row["org_right"]))): row for row in typed_rows
    }
    matrix_lookup = {
        tuple(sorted((row["org_left"], row["org_right"]))): row for row in matrix_rows
    }
    anchor_rows = []
    for anchor_kind, left, right in anchors:
        key = tuple(sorted((left, right)))
        typed = typed_lookup.get(key)
        anchor_rows.append(
            {
                "anchor_kind": anchor_kind,
                "org_left": key[0],
                "org_right": key[1],
                "matrix_pair_present": key in matrix_lookup,
                "typed_edge_present": typed is not None,
                "identity_edge_type_v1": typed["identity_edge_type_v1"] if typed else "",
                "identity_edge_basis_v1": typed["identity_edge_basis_v1"] if typed else "",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "owner_identity_typed_edges_v1.csv", typed_rows, list(typed_rows[0]))
    write_csv(
        output_dir / "owner_identity_typed_components_v1.csv",
        component_rows,
        list(component_rows[0]) if component_rows else ["component_id"],
    )
    write_csv(
        output_dir / "owner_identity_core_attachments_v1.csv",
        attachment_rows,
        list(attachment_rows[0]) if attachment_rows else ["org_left"],
    )
    write_csv(
        output_dir / "owner_identity_anchor_validation_v1.csv",
        anchor_rows,
        list(anchor_rows[0]),
    )

    edge_counts = Counter(row["identity_edge_type_v1"] for row in typed_rows)
    payload = {
        "schema_version": "owner_identity_typed_graph_v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "input_matrix": str(matrix_path),
        "input_matrix_row_count": len(matrix_rows),
        "typed_edge_count": len(typed_rows),
        "edge_type_counts": dict(sorted(edge_counts.items())),
        "typed_component_count": len(component_rows),
        "unvalidated_attachment_count": sum(
            row["attachment_status"] == "unvalidated_attachment_to_core"
            for row in attachment_rows
        ),
        "large_org_object_count_p90": round(large_org_threshold, 2),
        "rename_handoff_threshold": RENAME_HANDOFF_THRESHOLD,
        "interpretation_rules": [
            "Four-title evidence has priority and means disclosed production network.",
            "Rename requires handwriting, shared GIP, and temporal handoff.",
            "Shared-GIP handwriting without handoff is not called rename.",
            "Handwriting-only edges remain owner-or-template candidates.",
            "Components are built separately by edge type.",
            "Attachments never expand rename/network core components.",
        ],
    }
    write_json(output_dir / "owner_identity_typed_graph_v1.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.matrix, args.objects, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
