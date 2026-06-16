#!/usr/bin/env python3
"""Build section-level similarity clusters from pairwise comparison results."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PAIRWISE_CSV = Path(r"E:\output\DocSpectrum\comparison_results_v0_3_nk_34\comparison_results_v0_3.csv")
DEFAULT_DOCUMENTS_CSV = Path(r"E:\output\DocSpectrum\element_base_v0_nk_34\documents_index.csv")
DEFAULT_METADATA_CSV = Path(r"E:\output\DocSpectrum\cross_org_manifest_v0\cross_org_manifest_v0.csv")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\nk_section_clusters_v0")


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


def round_float(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.median(values)


def parse_thresholds(raw: str) -> list[float]:
    values = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(float(part))
    if not values:
        raise argparse.ArgumentTypeError("At least one threshold is required.")
    return sorted(set(values), reverse=True)


def load_metadata(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    rows = read_csv(path)
    return {row["object_id"]: row for row in rows if row.get("object_id")}


def object_sort_key(object_id: str) -> tuple[int, str]:
    prefix = object_id.split("_", 1)[0]
    try:
        return int(prefix), object_id
    except ValueError:
        return 10**9, object_id


def connected_components(nodes: set[str], edges: dict[str, set[str]]) -> list[list[str]]:
    components = []
    seen = set()
    for node in sorted(nodes, key=object_sort_key):
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(edges.get(current, set()), key=object_sort_key, reverse=True):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component, key=object_sort_key))
    components.sort(key=lambda item: (-len(item), object_sort_key(item[0]) if item else (0, "")))
    return components


def summarize_metadata(object_ids: list[str], metadata: dict[str, dict[str, str]]) -> dict[str, str]:
    addresses = []
    subgroups = set()
    contractors = set()
    main_groups = set()
    for object_id in object_ids:
        row = metadata.get(object_id, {})
        if row.get("address_normalized"):
            addresses.append(row["address_normalized"])
        elif row.get("address_raw"):
            addresses.append(row["address_raw"])
        if row.get("work_subgroup"):
            subgroups.add(row["work_subgroup"])
        if row.get("contractor"):
            contractors.add(row["contractor"])
        if row.get("main_group"):
            main_groups.add(row["main_group"])
    return {
        "addresses": " | ".join(addresses),
        "work_subgroups": " | ".join(sorted(subgroups)),
        "contractors": " | ".join(sorted(contractors)),
        "main_groups": " | ".join(sorted(main_groups)),
    }


def build(
    pairwise_csv: Path,
    documents_csv: Path,
    output_dir: Path,
    metadata_csv: Path | None,
    thresholds: list[float],
    metric_column: str,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    pair_rows = read_csv(pairwise_csv)
    document_rows = read_csv(documents_csv)
    metadata = load_metadata(metadata_csv)

    nodes_by_section: dict[str, set[str]] = defaultdict(set)
    bundles_by_section_object: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in document_rows:
        section_code = row["section_code"]
        if section_code == "UNKNOWN":
            continue
        object_id = row["object_id"]
        nodes_by_section[section_code].add(object_id)
        bundles_by_section_object[(section_code, object_id)].add(row["bundle_id"])

    pair_score: dict[tuple[str, str, str], float] = {}
    pair_axes: dict[tuple[str, str, str], dict[str, float]] = {}
    pair_count_by_section = defaultdict(int)
    for row in pair_rows:
        section_code = row["section_code"]
        left = row["left_object_id"]
        right = row["right_object_id"]
        key = (section_code, left, right) if object_sort_key(left) <= object_sort_key(right) else (section_code, right, left)
        score = safe_float(row.get(metric_column))
        pair_score[key] = score
        pair_axes[key] = {
            "text_segment": safe_float(row.get("text_segment_idf_jaccard")),
            "text_word_shingle": safe_float(row.get("text_word_shingle_idf_jaccard")),
            "table_cell_text": safe_float(row.get("table_cell_text_idf_jaccard")),
            "table_layout_signature": safe_float(row.get("table_layout_signature_idf_jaccard")),
            "table_content_signature": safe_float(row.get("table_content_signature_idf_jaccard")),
            "page_signature": safe_float(row.get("page_signature_idf_jaccard")),
        }
        pair_count_by_section[section_code] += 1

    component_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    cluster_id_counter = 0

    for section_code in sorted(nodes_by_section):
        nodes = nodes_by_section[section_code]
        section_values = [
            score
            for (pair_section, _left, _right), score in pair_score.items()
            if pair_section == section_code
        ]
        for threshold in thresholds:
            edges: dict[str, set[str]] = defaultdict(set)
            section_edge_count = 0
            for (pair_section, left, right), score in pair_score.items():
                if pair_section != section_code or score < threshold:
                    continue
                edges[left].add(right)
                edges[right].add(left)
                section_edge_count += 1

            components = connected_components(nodes, edges)
            non_singletons = [component for component in components if len(component) > 1]
            singleton_count = sum(1 for component in components if len(component) == 1)
            largest_size = max((len(component) for component in components), default=0)
            summary_rows.append(
                {
                    "section_code": section_code,
                    "threshold": threshold,
                    "object_count": len(nodes),
                    "pair_count": pair_count_by_section[section_code],
                    "edge_count_at_threshold": section_edge_count,
                    "component_count": len(components),
                    "non_singleton_component_count": len(non_singletons),
                    "singleton_count": singleton_count,
                    "largest_component_size": largest_size,
                    "section_median_score": round_float(median_or_none(section_values)),
                    "section_min_score": round_float(min(section_values) if section_values else None),
                    "section_max_score": round_float(max(section_values) if section_values else None),
                }
            )

            for component in components:
                cluster_id_counter += 1
                internal_scores = []
                internal_axes: dict[str, list[float]] = defaultdict(list)
                for idx, left in enumerate(component):
                    for right in component[idx + 1 :]:
                        key = (section_code, left, right) if object_sort_key(left) <= object_sort_key(right) else (
                            section_code,
                            right,
                            left,
                        )
                        if key not in pair_score:
                            continue
                        internal_scores.append(pair_score[key])
                        for axis_name, axis_value in pair_axes.get(key, {}).items():
                            internal_axes[axis_name].append(axis_value)
                meta = summarize_metadata(component, metadata)
                component_rows.append(
                    {
                        "cluster_id": f"cluster_{cluster_id_counter:05d}",
                        "section_code": section_code,
                        "threshold": threshold,
                        "component_size": len(component),
                        "object_ids": "|".join(component),
                        "bundle_ids": "|".join(
                            f"{object_id}:{','.join(sorted(bundles_by_section_object[(section_code, object_id)]))}"
                            for object_id in component
                        ),
                        "internal_pair_count": len(internal_scores),
                        "internal_score_median": round_float(median_or_none(internal_scores)),
                        "internal_score_min": round_float(min(internal_scores) if internal_scores else None),
                        "internal_score_max": round_float(max(internal_scores) if internal_scores else None),
                        "internal_text_segment_median": round_float(median_or_none(internal_axes["text_segment"])),
                        "internal_text_word_shingle_median": round_float(
                            median_or_none(internal_axes["text_word_shingle"])
                        ),
                        "internal_table_cell_text_median": round_float(median_or_none(internal_axes["table_cell_text"])),
                        "internal_table_layout_signature_median": round_float(
                            median_or_none(internal_axes["table_layout_signature"])
                        ),
                        "internal_table_content_signature_median": round_float(
                            median_or_none(internal_axes["table_content_signature"])
                        ),
                        "internal_page_signature_median": round_float(median_or_none(internal_axes["page_signature"])),
                        **meta,
                    }
                )

    write_csv(
        output_dir / "section_cluster_summary_v0.csv",
        summary_rows,
        [
            "section_code",
            "threshold",
            "object_count",
            "pair_count",
            "edge_count_at_threshold",
            "component_count",
            "non_singleton_component_count",
            "singleton_count",
            "largest_component_size",
            "section_median_score",
            "section_min_score",
            "section_max_score",
        ],
    )
    write_csv(
        output_dir / "section_clusters_v0.csv",
        component_rows,
        [
            "cluster_id",
            "section_code",
            "threshold",
            "component_size",
            "object_ids",
            "bundle_ids",
            "internal_pair_count",
            "internal_score_median",
            "internal_score_min",
            "internal_score_max",
            "internal_text_segment_median",
            "internal_text_word_shingle_median",
            "internal_table_cell_text_median",
            "internal_table_layout_signature_median",
            "internal_table_content_signature_median",
            "internal_page_signature_median",
            "work_subgroups",
            "contractors",
            "main_groups",
            "addresses",
        ],
    )
    write_json(
        output_dir / "section_clusters_v0.json",
        {
            "schema_version": "section_clusters_v0",
            "generated_at": generated_at,
            "pairwise_csv": str(pairwise_csv),
            "documents_csv": str(documents_csv),
            "metadata_csv": str(metadata_csv) if metadata_csv else None,
            "metric_column": metric_column,
            "thresholds": thresholds,
            "summary_csv": str(output_dir / "section_cluster_summary_v0.csv"),
            "clusters_csv": str(output_dir / "section_clusters_v0.csv"),
            "modeling_rules": [
                "Clusters are connected components of same-section object graphs.",
                "Edges are pairwise similarities greater than or equal to the selected threshold.",
                "Clusters are diagnostic and do not imply a known human author without external labels.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster same-section documents by pairwise similarity threshold.")
    parser.add_argument("--pairwise-csv", type=Path, default=DEFAULT_PAIRWISE_CSV)
    parser.add_argument("--documents-csv", type=Path, default=DEFAULT_DOCUMENTS_CSV)
    parser.add_argument("--metadata-csv", type=Path, default=DEFAULT_METADATA_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metric-column", default="idf_similarity_v0_3")
    parser.add_argument("--thresholds", type=parse_thresholds, default=parse_thresholds("0.75,0.60,0.45"))
    args = parser.parse_args()
    build(args.pairwise_csv, args.documents_csv, args.output_dir, args.metadata_csv, args.thresholds, args.metric_column)


if __name__ == "__main__":
    main()
