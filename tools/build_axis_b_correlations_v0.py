#!/usr/bin/env python3
"""Build Axis B TEI/count correlation exports.

Axis B validates size/TEI effects with absolute document/entity counts. This is
a read-only eval/profile layer and does not change core scoring.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
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

DOCUMENT_COUNT_METRICS = [
    "page_count",
    "element_count",
    "visible_element_count",
    "text_segment_count",
    "table_count",
    "table_cell_count",
    "image_count",
    "layer_count",
    "total_text_chars",
    "total_text_words",
    "group_text_count",
    "group_lines_count",
    "group_frames_count",
    "group_images_count",
    "group_tables_count",
    "group_other_vector_count",
]

DOCUMENT_RATIO_METRICS = [
    "elements_per_page",
    "text_segments_per_page",
    "tables_per_page",
    "table_cells_per_page",
    "images_per_page",
    "table_cells_per_table",
    "text_segment_ratio",
    "image_ratio",
    "table_ratio",
    "group_text_ratio",
    "group_lines_ratio",
    "group_frames_ratio",
    "group_images_ratio",
    "group_tables_ratio",
    "group_other_vector_ratio",
]

ENTITY_METRICS = [
    "entity_occurrence_count",
    "entity_unique_count",
    "entity_typical_occurrences",
    "entity_shared_rare_occurrences",
    "entity_original_occurrences",
]


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
    if len(left) < 3 or len(left) != len(right):
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
    if len(left) < 3 or len(left) != len(right):
        return None
    return pearson(rankdata(left), rankdata(right))


def load_objects(path: Path) -> dict[str, dict[str, str]]:
    return {row["object_id"]: row for row in read_csv(path)}


def load_entity_summaries(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row["object_id"], row["bundle_id"], row["entity_kind"]): row
        for row in read_csv(path)
    }


def quantile_thresholds(values: list[float]) -> tuple[float | None, float | None]:
    if len(values) < 4:
        return None, None
    ordered = sorted(values)
    return ordered[len(ordered) // 4], ordered[(len(ordered) * 3) // 4]


def bucket_for(value: float | None, low: float | None, high: float | None) -> str:
    if value is None or low is None or high is None:
        return "unknown"
    if value <= low:
        return "low"
    if value >= high:
        return "high"
    return "mid"


def median_or_blank(values: list[float]) -> float | str:
    if not values:
        return ""
    return round_float(statistics.median(values))


def build_joined_rows(
    documents: list[dict[str, str]],
    objects: dict[str, dict[str, str]],
    entity_summaries: dict[tuple[str, str, str], dict[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    entity_kinds = sorted({key[2] for key in entity_summaries})
    for doc in documents:
        obj = objects.get(doc["object_id"], {})
        base: dict[str, Any] = {
            "object_id": doc["object_id"],
            "bundle_id": doc["bundle_id"],
            "section_code": doc["section_code"],
            "project_subgroup": obj.get("project_subgroup", ""),
            "address_normalized": obj.get("address_normalized", ""),
            "file_name": doc.get("file_name", ""),
        }
        for feature in TEI_FEATURES:
            base[feature] = obj.get(feature, "")
        for metric in DOCUMENT_COUNT_METRICS + DOCUMENT_RATIO_METRICS:
            base[metric] = doc.get(metric, "")

        for entity_kind in entity_kinds:
            entity = entity_summaries.get((doc["object_id"], doc["bundle_id"], entity_kind), {})
            prefix = f"entity_{entity_kind}"
            base[f"{prefix}_occurrence_count"] = entity.get("occurrence_count", "0")
            base[f"{prefix}_unique_count"] = entity.get("unique_entity_count", "0")
            base[f"{prefix}_typical_occurrences"] = entity.get("typical_occurrences", "0")
            base[f"{prefix}_shared_rare_occurrences"] = entity.get("shared_rare_occurrences", "0")
            base[f"{prefix}_original_occurrences"] = entity.get("original_occurrences", "0")
        rows.append(base)
    return rows


def correlation_rows(joined_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    section_codes = sorted({row["section_code"] for row in joined_rows})
    metric_names = DOCUMENT_COUNT_METRICS + DOCUMENT_RATIO_METRICS
    entity_metric_names = [
        key
        for key in sorted(joined_rows[0])
        if key.startswith("entity_") and (
            key.endswith("_occurrence_count")
            or key.endswith("_unique_count")
            or key.endswith("_typical_occurrences")
            or key.endswith("_shared_rare_occurrences")
            or key.endswith("_original_occurrences")
        )
    ] if joined_rows else []
    metric_names.extend(entity_metric_names)

    for section_code in section_codes:
        section_rows = [row for row in joined_rows if row["section_code"] == section_code]
        for tei_feature in TEI_FEATURES:
            for metric_name in metric_names:
                pairs = [
                    (tei_value, metric_value)
                    for row in section_rows
                    if (tei_value := safe_float(row.get(tei_feature))) is not None
                    and (metric_value := safe_float(row.get(metric_name))) is not None
                ]
                if len(pairs) < 4:
                    continue
                tei_values = [item[0] for item in pairs]
                metric_values = [item[1] for item in pairs]
                corr = spearman(tei_values, metric_values)
                if corr is None:
                    continue
                rows.append(
                    {
                        "section_code": section_code,
                        "tei_feature": tei_feature,
                        "metric_name": metric_name,
                        "metric_family": "entity" if metric_name.startswith("entity_") else (
                            "document_ratio" if metric_name in DOCUMENT_RATIO_METRICS else "document_count"
                        ),
                        "n": len(pairs),
                        "spearman": round_float(corr),
                        "abs_spearman": round_float(abs(corr)),
                        "direction": "positive" if corr > 0 else "negative" if corr < 0 else "zero",
                    }
                )
    rows.sort(key=lambda row: (-metric_float(row["abs_spearman"]), row["section_code"], row["tei_feature"]))
    return rows


def bucket_summary_rows(joined_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    bucket_features = [
        "tei_norm_building_volume_m3",
        "tei_norm_floors_count",
        "tei_norm_height_m",
        "tei_norm_total_area_m2",
    ]
    summary_metrics = [
        "page_count",
        "element_count",
        "table_count",
        "table_cell_count",
        "total_text_words",
        "group_lines_count",
        "group_frames_count",
        "group_tables_count",
    ]
    for feature in bucket_features:
        values = [parsed for row in joined_rows if (parsed := safe_float(row.get(feature))) is not None]
        low, high = quantile_thresholds(values)
        for section_code in sorted({row["section_code"] for row in joined_rows}):
            section_rows = [row for row in joined_rows if row["section_code"] == section_code]
            for bucket in ["low", "mid", "high", "unknown"]:
                bucket_rows = [
                    row for row in section_rows
                    if bucket_for(safe_float(row.get(feature)), low, high) == bucket
                ]
                if not bucket_rows:
                    continue
                row: dict[str, Any] = {
                    "section_code": section_code,
                    "tei_feature": feature,
                    "bucket": bucket,
                    "document_count": len(bucket_rows),
                    "bucket_low_threshold": round_float(low),
                    "bucket_high_threshold": round_float(high),
                }
                for metric in summary_metrics:
                    row[f"median_{metric}"] = median_or_blank([
                        parsed for item in bucket_rows if (parsed := safe_float(item.get(metric))) is not None
                    ])
                rows.append(row)
    rows.sort(key=lambda row: (row["section_code"], row["tei_feature"], row["bucket"]))
    return rows


def build(
    object_registry_path: Path,
    documents_index_path: Path,
    section_typicality_path: Path,
    output_dir: Path,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    objects = load_objects(object_registry_path)
    documents = read_csv(documents_index_path)
    entity_summaries = load_entity_summaries(section_typicality_path)
    joined_rows = build_joined_rows(documents, objects, entity_summaries)
    corr_rows = correlation_rows(joined_rows)
    bucket_rows = bucket_summary_rows(joined_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    joined_fields = list(joined_rows[0].keys()) if joined_rows else []
    write_csv(output_dir / "axis_b_document_metrics_v0.csv", joined_rows, joined_fields)
    write_csv(
        output_dir / "axis_b_correlations_v0.csv",
        corr_rows,
        [
            "section_code",
            "tei_feature",
            "metric_name",
            "metric_family",
            "n",
            "spearman",
            "abs_spearman",
            "direction",
        ],
    )
    bucket_fields = list(bucket_rows[0].keys()) if bucket_rows else []
    write_csv(output_dir / "axis_b_tei_bucket_summary_v0.csv", bucket_rows, bucket_fields)

    top_rows = corr_rows[:25]
    summary = {
        "schema_version": "axis_b_correlations_v0",
        "generated_at": generated_at,
        "object_registry_path": str(object_registry_path),
        "documents_index_path": str(documents_index_path),
        "section_typicality_path": str(section_typicality_path),
        "output_dir": str(output_dir),
        "document_metric_rows": len(joined_rows),
        "correlation_rows": len(corr_rows),
        "bucket_summary_rows": len(bucket_rows),
        "tei_features": TEI_FEATURES,
        "document_count_metrics": DOCUMENT_COUNT_METRICS,
        "document_ratio_metrics": DOCUMENT_RATIO_METRICS,
        "top_abs_spearman": top_rows,
        "modeling_rules": [
            "Axis B measures size/count relations, not content jaccard.",
            "TEI/domain fields remain eval/profile context and do not enter core scoring.",
            "Spearman rank correlation is preferred because equipment choices are stepped.",
            "Document size controls are exposed through page_count and per-page ratios.",
        ],
        "files": {
            "document_metrics": "axis_b_document_metrics_v0.csv",
            "correlations": "axis_b_correlations_v0.csv",
            "tei_bucket_summary": "axis_b_tei_bucket_summary_v0.csv",
        },
    }
    write_json(output_dir / "axis_b_correlations_v0.json", summary)

    readme = f"""# axis_b_correlations_v0

Axis B TEI/count correlation exports for DocSpectrum.

Generated at:

- `{generated_at}`

Inputs:

- object registry: `{object_registry_path}`
- documents index: `{documents_index_path}`
- section typicality: `{section_typicality_path}`

Key policy:

- This is an eval/profile layer, not a scoring layer.
- TEI features are not used in core similarity scoring.
- Rank correlations are used because engineering components follow stepped nominal sizes.
- Document size controls are exposed through page count and per-page ratios.
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
        "--documents-index",
        default=r"E:\output\DocSpectrum\element_base_v0_18_n2\documents_index.csv",
        help="Document index from element_base_v0.",
    )
    parser.add_argument(
        "--section-typicality",
        default=r"E:\output\DocSpectrum\corpus_frequency_v0_18_n2\section_typicality_v0.csv",
        help="Section typicality CSV from corpus_frequency_v0.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\output\DocSpectrum\axis_b_correlations_v0_18_n2",
        help="Directory for Axis B correlation artifacts.",
    )
    args = parser.parse_args()
    build(
        Path(args.object_registry),
        Path(args.documents_index),
        Path(args.section_typicality),
        Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
