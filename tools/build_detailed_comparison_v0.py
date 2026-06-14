#!/usr/bin/env python3
"""Build detailed exploratory comparison_result_v0 artifacts.

The fast comparison in compare_pairs_v0.py gives scores. This script explains
those scores: feature deltas, matching page signatures, matching table
signatures, and exact normalized text-segment overlap.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NUMERIC_FEATURES = [
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
    "broken_encoding_count",
    "elements_per_page",
    "text_segments_per_page",
    "tables_per_page",
    "table_cells_per_page",
    "images_per_page",
    "table_cells_per_table",
    "text_segment_ratio",
    "image_ratio",
    "table_ratio",
    "max_elements_on_page",
    "max_text_segments_on_page",
    "group_text_count",
    "group_text_ratio",
    "group_lines_count",
    "group_lines_ratio",
    "group_frames_count",
    "group_frames_ratio",
    "group_images_count",
    "group_images_ratio",
    "group_tables_count",
    "group_tables_ratio",
    "group_other_vector_count",
    "group_other_vector_ratio",
]


FEATURE_COSINE_FEATURES = [
    "page_count",
    "elements_per_page",
    "text_segments_per_page",
    "tables_per_page",
    "table_cells_per_page",
    "images_per_page",
    "table_cells_per_table",
    "text_segment_ratio",
    "image_ratio",
    "table_ratio",
    "max_elements_on_page",
    "max_text_segments_on_page",
    "group_text_ratio",
    "group_lines_ratio",
    "group_frames_ratio",
    "group_images_ratio",
    "group_tables_ratio",
    "group_other_vector_ratio",
]


FEATURE_SUBVECTORS = {
    "volume": [
        "page_count",
        "element_count",
        "visible_element_count",
        "layer_count",
    ],
    "density": [
        "elements_per_page",
        "max_elements_on_page",
        "max_text_segments_on_page",
    ],
    "text": [
        "text_segment_count",
        "total_text_chars",
        "total_text_words",
        "text_segments_per_page",
        "text_segment_ratio",
        "group_text_count",
        "group_text_ratio",
    ],
    "tables": [
        "table_count",
        "table_cell_count",
        "tables_per_page",
        "table_cells_per_page",
        "table_cells_per_table",
        "table_ratio",
        "group_tables_count",
        "group_tables_ratio",
    ],
    "graphics": [
        "image_count",
        "images_per_page",
        "image_ratio",
        "group_images_count",
        "group_images_ratio",
        "group_lines_count",
        "group_lines_ratio",
        "group_frames_count",
        "group_frames_ratio",
        "group_other_vector_count",
        "group_other_vector_ratio",
    ],
    "element_mix": [
        "group_text_ratio",
        "group_lines_ratio",
        "group_frames_ratio",
        "group_images_ratio",
        "group_tables_ratio",
        "group_other_vector_ratio",
    ],
}


SECTION_ORDER = {
    "АР": 10,
    "КР": 20,
    "ПОКР": 30,
    "ИД": 40,
    "ИОС5.1": 50,
    "ИОС5.4.1": 60,
    "ИОС5.5.1": 70,
    "СМ": 80,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if value in ("", None):
            return 0
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def log_vector(row: dict[str, str], features: list[str]) -> list[float]:
    return [math.log1p(max(0.0, safe_float(row.get(feature)))) for feature in features]


def centered_vector(
    row: dict[str, str],
    features: list[str],
    feature_stats: dict[str, dict[str, float]],
) -> list[float]:
    values = []
    for feature in features:
        stats = feature_stats[feature]
        values.append((safe_float(row.get(feature)) - stats["mean"]) / stats["stdev"])
    return values


def multiset_jaccard(left: Counter[str], right: Counter[str]) -> float:
    if not left and not right:
        return 0.0
    keys = set(left) | set(right)
    intersection = sum(min(left[key], right[key]) for key in keys)
    union = sum(max(left[key], right[key]) for key in keys)
    if not union:
        return 0.0
    return intersection / union


def rows_for(rows: list[dict[str, str]], object_id: str, bundle_id: str) -> list[dict[str, str]]:
    return [
        row for row in rows
        if row.get("object_id") == object_id and row.get("bundle_id") == bundle_id
    ]


def counter_for(rows: list[dict[str, str]], signature_field: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        signature = row.get(signature_field)
        if signature:
            counter[signature] += 1
    return counter


def rows_by_signature(
    rows: list[dict[str, str]],
    signature_field: str,
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        signature = row.get(signature_field)
        if signature:
            grouped[signature].append(row)
    return grouped


def page_ref(row: dict[str, str]) -> dict[str, Any]:
    return {
        "page_number": safe_int(row.get("page_number")),
        "page_size_key": row.get("page_size_key", ""),
        "element_count": safe_int(row.get("element_count")),
        "text_count": safe_int(row.get("text_count")),
        "line_count": safe_int(row.get("line_count")),
        "frame_count": safe_int(row.get("frame_count")),
        "image_count": safe_int(row.get("image_count")),
        "table_count": safe_int(row.get("table_count")),
    }


def table_ref(row: dict[str, str]) -> dict[str, Any]:
    return {
        "table_id": row.get("table_id", ""),
        "page_number": safe_int(row.get("page_number")),
        "row_count": safe_int(row.get("row_count")),
        "column_count": safe_int(row.get("column_count")),
        "cell_count": safe_int(row.get("cell_count")),
        "bbox_area": round_float(safe_float(row.get("bbox_area")), 2),
        "layout_signature_source": row.get("layout_signature_source", ""),
    }


def signature_matches(
    left_rows: list[dict[str, str]],
    right_rows: list[dict[str, str]],
    signature_field: str,
    row_ref,
    limit: int = 30,
) -> dict[str, Any]:
    left_grouped = rows_by_signature(left_rows, signature_field)
    right_grouped = rows_by_signature(right_rows, signature_field)
    shared = []
    for signature in set(left_grouped) & set(right_grouped):
        left_items = sorted(left_grouped[signature], key=lambda row: safe_int(row.get("page_number")))
        right_items = sorted(right_grouped[signature], key=lambda row: safe_int(row.get("page_number")))
        shared.append(
            {
                "signature": signature,
                "left_count": len(left_items),
                "right_count": len(right_items),
                "shared_count": min(len(left_items), len(right_items)),
                "left_refs": [row_ref(row) for row in left_items[:10]],
                "right_refs": [row_ref(row) for row in right_items[:10]],
            }
        )
    shared.sort(key=lambda item: (-item["shared_count"], item["signature"]))

    left_only = []
    for signature in sorted(set(left_grouped) - set(right_grouped)):
        left_only.append(
            {
                "signature": signature,
                "count": len(left_grouped[signature]),
                "refs": [row_ref(row) for row in left_grouped[signature][:10]],
            }
        )
    right_only = []
    for signature in sorted(set(right_grouped) - set(left_grouped)):
        right_only.append(
            {
                "signature": signature,
                "count": len(right_grouped[signature]),
                "refs": [row_ref(row) for row in right_grouped[signature][:10]],
            }
        )

    left_counter = Counter({key: len(value) for key, value in left_grouped.items()})
    right_counter = Counter({key: len(value) for key, value in right_grouped.items()})
    return {
        "jaccard": round_float(multiset_jaccard(left_counter, right_counter)),
        "shared_signature_count": len(shared),
        "left_unique_signature_count": len(left_grouped),
        "right_unique_signature_count": len(right_grouped),
        "left_only_signature_count": len(left_only),
        "right_only_signature_count": len(right_only),
        "shared_top": shared[:limit],
        "left_only_top": sorted(left_only, key=lambda item: (-item["count"], item["signature"]))[:limit],
        "right_only_top": sorted(right_only, key=lambda item: (-item["count"], item["signature"]))[:limit],
    }


def exact_page_number_matches(
    left_pages: list[dict[str, str]],
    right_pages: list[dict[str, str]],
) -> list[dict[str, Any]]:
    left_by_number = {safe_int(row.get("page_number")): row for row in left_pages}
    right_by_number = {safe_int(row.get("page_number")): row for row in right_pages}
    matches = []
    for page_number in sorted(set(left_by_number) & set(right_by_number)):
        left = left_by_number[page_number]
        right = right_by_number[page_number]
        if left.get("page_signature") == right.get("page_signature"):
            matches.append(
                {
                    "page_number": page_number,
                    "signature": left.get("page_signature"),
                    "left": page_ref(left),
                    "right": page_ref(right),
                }
            )
    return matches


def feature_deltas(left: dict[str, str], right: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for feature in NUMERIC_FEATURES:
        left_value = safe_float(left.get(feature))
        right_value = safe_float(right.get(feature))
        delta = right_value - left_value
        base = max(abs(left_value), abs(right_value), 1.0)
        rows.append(
            {
                "feature": feature,
                "left_value": round_float(left_value),
                "right_value": round_float(right_value),
                "delta_right_minus_left": round_float(delta),
                "relative_delta": round_float(delta / base),
                "abs_relative_delta": round_float(abs(delta) / base),
            }
        )
    rows.sort(key=lambda item: (-item["abs_relative_delta"], item["feature"]))
    return rows


def build_feature_stats(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    features = sorted(set(NUMERIC_FEATURES) | set(FEATURE_COSINE_FEATURES))
    stats = {}
    for feature in features:
        values = [safe_float(row.get(feature)) for row in rows]
        mean = sum(values) / len(values) if values else 0.0
        variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
        stdev = math.sqrt(variance) or 1.0
        stats[feature] = {"mean": mean, "stdev": stdev}
    return stats


def relative_delta_summary(
    left: dict[str, str],
    right: dict[str, str],
    features: list[str],
) -> dict[str, Any]:
    deltas = []
    for feature in features:
        left_value = safe_float(left.get(feature))
        right_value = safe_float(right.get(feature))
        base = max(abs(left_value), abs(right_value), 1.0)
        deltas.append(abs(right_value - left_value) / base)
    return {
        "mean_abs_relative_delta": round_float(sum(deltas) / len(deltas)) if deltas else 0.0,
        "max_abs_relative_delta": round_float(max(deltas)) if deltas else 0.0,
    }


def feature_subvector_cosines(
    left: dict[str, str],
    right: dict[str, str],
    feature_stats: dict[str, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    result = {}
    for subvector_name, features in FEATURE_SUBVECTORS.items():
        subvector_cosine = cosine(log_vector(left, features), log_vector(right, features))
        centered_cosine = cosine(
            centered_vector(left, features, feature_stats),
            centered_vector(right, features, feature_stats),
        )
        delta_summary = relative_delta_summary(left, right, features)
        result[subvector_name] = {
            "cosine": round_float(subvector_cosine),
            "centered_cosine": round_float(centered_cosine),
            **delta_summary,
            "feature_count": len(features),
            "features": features,
        }
    return result


def text_segment_counter(export_root: Path, object_id: str, bundle_id: str) -> Counter[str]:
    path = export_root / object_id / bundle_id / "text_segments.csv"
    counter: Counter[str] = Counter()
    for row in read_csv(path):
        text = " ".join((row.get("normalized_text") or row.get("text_value") or "").split()).lower()
        if len(text) < 15:
            continue
        counter[text] += 1
    return counter


def text_overlap(
    export_root: Path,
    left_key: tuple[str, str],
    right_key: tuple[str, str],
    limit: int = 30,
) -> dict[str, Any]:
    left = text_segment_counter(export_root, *left_key)
    right = text_segment_counter(export_root, *right_key)
    shared = []
    for text in set(left) & set(right):
        shared.append(
            {
                "text_sha1": sha1_text(text),
                "left_count": left[text],
                "right_count": right[text],
                "shared_count": min(left[text], right[text]),
                "char_count": len(text),
            }
        )
    shared.sort(key=lambda item: (-item["shared_count"], -item["char_count"], item["text_sha1"]))
    return {
        "left_comparable_segment_count": sum(left.values()),
        "right_comparable_segment_count": sum(right.values()),
        "left_unique_segment_count": len(left),
        "right_unique_segment_count": len(right),
        "shared_unique_segment_count": len(shared),
        "shared_multiset_count": sum(item["shared_count"] for item in shared),
        "exact_text_segment_jaccard": round_float(multiset_jaccard(left, right)),
        "shared_top": shared[:limit],
    }


def build(base_dir: Path, export_root: Path, output_dir: Path, section: str | None) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    features = read_csv(base_dir / "feature_matrix_v0.csv")
    feature_stats = build_feature_stats(features)
    pairs = read_csv(base_dir / "comparison_pairs_v0.csv")
    pages = read_csv(base_dir / "page_signatures_v0.csv")
    tables = read_csv(base_dir / "table_signatures_v0.csv")

    if section:
        pairs = [pair for pair in pairs if pair.get("section_code") == section]

    features_by_key = {
        (row["object_id"], row["bundle_id"]): row
        for row in features
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    for pair in sorted(pairs, key=lambda row: SECTION_ORDER.get(row.get("section_code", ""), 999)):
        left_key = (pair["left_object_id"], pair["left_bundle_id"])
        right_key = (pair["right_object_id"], pair["right_bundle_id"])
        left = features_by_key[left_key]
        right = features_by_key[right_key]

        left_pages = rows_for(pages, *left_key)
        right_pages = rows_for(pages, *right_key)
        left_tables = rows_for(tables, *left_key)
        right_tables = rows_for(tables, *right_key)

        page_axis = signature_matches(
            left_pages,
            right_pages,
            "page_signature",
            page_ref,
        )
        table_layout_axis = signature_matches(
            left_tables,
            right_tables,
            "layout_signature",
            table_ref,
        )
        table_content_axis = signature_matches(
            left_tables,
            right_tables,
            "content_sha1",
            table_ref,
        )
        text_axis = text_overlap(export_root, left_key, right_key)

        feature_cosine = cosine(
            log_vector(left, FEATURE_COSINE_FEATURES),
            log_vector(right, FEATURE_COSINE_FEATURES),
        )
        subvector_cosines = feature_subvector_cosines(left, right, feature_stats)
        detailed_similarity = (
            0.35 * feature_cosine
            + 0.20 * page_axis["jaccard"]
            + 0.15 * table_layout_axis["jaccard"]
            + 0.15 * table_content_axis["jaccard"]
            + 0.15 * text_axis["exact_text_segment_jaccard"]
        )

        exact_page_matches = exact_page_number_matches(left_pages, right_pages)
        deltas = feature_deltas(left, right)
        result = {
            "schema_version": "detailed_comparison_result_v0",
            "generated_at": generated_at,
            "pair_id": pair["pair_id"],
            "comparison_mode": pair["comparison_mode"],
            "section_code": pair["section_code"],
            "left": {
                "object_id": left["object_id"],
                "bundle_id": left["bundle_id"],
                "crc32": left["crc32"],
                "file_name": left["file_name"],
            },
            "right": {
                "object_id": right["object_id"],
                "bundle_id": right["bundle_id"],
                "crc32": right["crc32"],
                "file_name": right["file_name"],
            },
            "similarity_summary": {
                "detailed_similarity_v0": round_float(detailed_similarity),
                "feature_cosine_v0": round_float(feature_cosine),
                "feature_subvector_cosines": subvector_cosines,
                "page_signature_jaccard": page_axis["jaccard"],
                "table_layout_jaccard": table_layout_axis["jaccard"],
                "table_content_jaccard": table_content_axis["jaccard"],
                "exact_text_segment_jaccard": text_axis["exact_text_segment_jaccard"],
                "coverage": {
                    "numeric_features": len(FEATURE_COSINE_FEATURES),
                    "feature_delta_count": len(NUMERIC_FEATURES),
                    "feature_subvectors": {
                        name: payload["feature_count"]
                        for name, payload in subvector_cosines.items()
                    },
                    "axes": [
                        "feature_vector",
                        "feature_subvectors",
                        "page_signature",
                        "table_layout",
                        "table_content",
                        "exact_text_segments",
                    ],
                },
            },
            "axis_breakdown": {
                "feature_vector": {
                    "cosine": round_float(feature_cosine),
                    "subvector_cosines": subvector_cosines,
                    "largest_deltas_top": deltas[:15],
                    "all_deltas": deltas,
                },
                "page_signatures": {
                    **page_axis,
                    "same_page_number_exact_matches": exact_page_matches,
                    "same_page_number_exact_match_count": len(exact_page_matches),
                },
                "table_layout_signatures": table_layout_axis,
                "table_content_signatures": table_content_axis,
                "exact_text_segments": text_axis,
            },
            "interpretation_v0": {
                "scope": (
                    "Exploratory same-section comparison. Scores and weights are "
                    "temporary and intended to expose useful signals."
                ),
                "important_caution": (
                    "Exact page layout matches alone are not proof of document "
                    "reuse; they must be interpreted together with table, text, "
                    "graphic, and domain-specific signals."
                ),
            },
        }

        result_path = output_dir / f"{pair['pair_id']}.json"
        write_json(result_path, result)
        summary_rows.append(
            {
                "pair_id": pair["pair_id"],
                "section_code": pair["section_code"],
                "left_bundle_id": left["bundle_id"],
                "left_crc32": left["crc32"],
                "right_bundle_id": right["bundle_id"],
                "right_crc32": right["crc32"],
                "detailed_similarity_v0": round_float(detailed_similarity),
                "feature_cosine_v0": round_float(feature_cosine),
                "subvector_volume_cosine": subvector_cosines["volume"]["cosine"],
                "subvector_volume_centered_cosine": subvector_cosines["volume"]["centered_cosine"],
                "subvector_density_cosine": subvector_cosines["density"]["cosine"],
                "subvector_density_centered_cosine": subvector_cosines["density"]["centered_cosine"],
                "subvector_text_cosine": subvector_cosines["text"]["cosine"],
                "subvector_text_centered_cosine": subvector_cosines["text"]["centered_cosine"],
                "subvector_tables_cosine": subvector_cosines["tables"]["cosine"],
                "subvector_tables_centered_cosine": subvector_cosines["tables"]["centered_cosine"],
                "subvector_graphics_cosine": subvector_cosines["graphics"]["cosine"],
                "subvector_graphics_centered_cosine": subvector_cosines["graphics"]["centered_cosine"],
                "subvector_element_mix_cosine": subvector_cosines["element_mix"]["cosine"],
                "subvector_element_mix_centered_cosine": subvector_cosines["element_mix"]["centered_cosine"],
                "page_signature_jaccard": page_axis["jaccard"],
                "table_layout_jaccard": table_layout_axis["jaccard"],
                "table_content_jaccard": table_content_axis["jaccard"],
                "exact_text_segment_jaccard": text_axis["exact_text_segment_jaccard"],
                "same_page_number_exact_match_count": len(exact_page_matches),
                "shared_page_signature_count": page_axis["shared_signature_count"],
                "shared_table_layout_signature_count": table_layout_axis["shared_signature_count"],
                "shared_table_content_signature_count": table_content_axis["shared_signature_count"],
                "shared_text_unique_segment_count": text_axis["shared_unique_segment_count"],
                "result_path": str(result_path),
            }
        )

    summary_rows.sort(key=lambda row: SECTION_ORDER.get(row["section_code"], 999))
    write_csv(
        output_dir / "detailed_comparison_results_v0.csv",
        summary_rows,
        [
            "pair_id",
            "section_code",
            "left_bundle_id",
            "left_crc32",
            "right_bundle_id",
            "right_crc32",
            "detailed_similarity_v0",
            "feature_cosine_v0",
            "subvector_volume_cosine",
            "subvector_volume_centered_cosine",
            "subvector_density_cosine",
            "subvector_density_centered_cosine",
            "subvector_text_cosine",
            "subvector_text_centered_cosine",
            "subvector_tables_cosine",
            "subvector_tables_centered_cosine",
            "subvector_graphics_cosine",
            "subvector_graphics_centered_cosine",
            "subvector_element_mix_cosine",
            "subvector_element_mix_centered_cosine",
            "page_signature_jaccard",
            "table_layout_jaccard",
            "table_content_jaccard",
            "exact_text_segment_jaccard",
            "same_page_number_exact_match_count",
            "shared_page_signature_count",
            "shared_table_layout_signature_count",
            "shared_table_content_signature_count",
            "shared_text_unique_segment_count",
            "result_path",
        ],
    )
    write_json(
        output_dir / "detailed_comparison_results_v0.json",
        {
            "schema_version": "detailed_comparison_results_v0_index",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "export_root": str(export_root),
            "output_dir": str(output_dir),
            "pair_count": len(summary_rows),
            "sections": [row["section_code"] for row in summary_rows],
            "files": {
                "summary": "detailed_comparison_results_v0.csv",
                "pair_json": "*.json",
            },
        },
    )
    readme = f"""# detailed_comparison_results_v0

Detailed exploratory comparisons for `element_base_v0`.

Generated at:

- `{generated_at}`

The detailed result expands the fast comparison into:

- numeric feature deltas;
- exact page-signature matches and mismatches;
- table layout-signature matches and mismatches;
- table content-signature matches and mismatches;
- exact normalized text-segment overlap.

These artifacts are research outputs. They explain signals but are not final
expert conclusions.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=r"E:\repos\DocSpectrum\samples\element_base_v0",
        help="Directory with element_base_v0 artifacts.",
    )
    parser.add_argument(
        "--export-root",
        default=r"E:\output\DocSpectrum\export",
        help="Root directory with explorer exports.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\repos\DocSpectrum\samples\detailed_comparison_results_v0",
        help="Directory for detailed comparison artifacts.",
    )
    parser.add_argument(
        "--section",
        default=None,
        help="Optional section code filter, for example ИОС5.4.1.",
    )
    args = parser.parse_args()
    build(Path(args.base_dir), Path(args.export_root), Path(args.output_dir), args.section)


if __name__ == "__main__":
    main()
