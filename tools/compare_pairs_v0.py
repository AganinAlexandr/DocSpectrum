#!/usr/bin/env python3
"""Create the first same-section comparison results for element_base_v0."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NUMERIC_FEATURES = [
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


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def log_vector(row: dict[str, str], features: list[str]) -> list[float]:
    values = []
    for feature in features:
        value = max(0.0, safe_float(row.get(feature)))
        values.append(math.log1p(value))
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


def counter_for(
    rows: list[dict[str, str]],
    object_id: str,
    bundle_id: str,
    signature_field: str,
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        if row.get("object_id") == object_id and row.get("bundle_id") == bundle_id:
            signature = row.get(signature_field)
            if signature:
                counter[signature] += 1
    return counter


def top_common(left: Counter[str], right: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    shared = []
    for signature in set(left) & set(right):
        shared.append(
            {
                "signature": signature,
                "left_count": left[signature],
                "right_count": right[signature],
                "shared_count": min(left[signature], right[signature]),
            }
        )
    shared.sort(key=lambda item: (-item["shared_count"], item["signature"]))
    return shared[:limit]


def build(base_dir: Path, output_dir: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    features = read_csv(base_dir / "feature_matrix_v0.csv")
    pairs = read_csv(base_dir / "comparison_pairs_v0.csv")
    pages = read_csv(base_dir / "page_signatures_v0.csv")
    tables = read_csv(base_dir / "table_signatures_v0.csv")

    features_by_key = {
        (row["object_id"], row["bundle_id"]): row
        for row in features
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    pair_result_rows = []
    for pair in pairs:
        left_key = (pair["left_object_id"], pair["left_bundle_id"])
        right_key = (pair["right_object_id"], pair["right_bundle_id"])
        left = features_by_key[left_key]
        right = features_by_key[right_key]

        feature_cosine = cosine(log_vector(left, NUMERIC_FEATURES), log_vector(right, NUMERIC_FEATURES))

        left_pages = counter_for(pages, *left_key, "page_signature")
        right_pages = counter_for(pages, *right_key, "page_signature")
        page_jaccard = multiset_jaccard(left_pages, right_pages)

        left_table_layouts = counter_for(tables, *left_key, "layout_signature")
        right_table_layouts = counter_for(tables, *right_key, "layout_signature")
        table_layout_jaccard = multiset_jaccard(left_table_layouts, right_table_layouts)

        left_table_content = counter_for(tables, *left_key, "content_sha1")
        right_table_content = counter_for(tables, *right_key, "content_sha1")
        table_content_jaccard = multiset_jaccard(left_table_content, right_table_content)

        weighted_similarity = (
            0.55 * feature_cosine
            + 0.20 * page_jaccard
            + 0.15 * table_layout_jaccard
            + 0.10 * table_content_jaccard
        )

        result = {
            "schema_version": "comparison_result_v0",
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
                "weighted_similarity_v0": round_float(weighted_similarity),
                "feature_cosine_v0": round_float(feature_cosine),
                "page_signature_jaccard": round_float(page_jaccard),
                "table_layout_jaccard": round_float(table_layout_jaccard),
                "table_content_jaccard": round_float(table_content_jaccard),
                "coverage": {
                    "numeric_features": len(NUMERIC_FEATURES),
                    "axes": [
                        "feature_vector",
                        "page_signature",
                        "table_layout",
                        "table_content",
                    ],
                },
            },
            "shared_signatures": {
                "pages_top": top_common(left_pages, right_pages),
                "table_layouts_top": top_common(left_table_layouts, right_table_layouts),
                "table_content_top": top_common(left_table_content, right_table_content),
            },
            "v0_note": (
                "This result is an exploratory measurement, not a final expert "
                "conclusion. Weights and feature sets are intentionally simple."
            ),
        }

        result_path = output_dir / f"{pair['pair_id']}.json"
        write_json(result_path, result)
        pair_result_rows.append(
            {
                "pair_id": pair["pair_id"],
                "section_code": pair["section_code"],
                "left_object_id": left["object_id"],
                "left_bundle_id": left["bundle_id"],
                "left_crc32": left["crc32"],
                "right_object_id": right["object_id"],
                "right_bundle_id": right["bundle_id"],
                "right_crc32": right["crc32"],
                "weighted_similarity_v0": round_float(weighted_similarity),
                "feature_cosine_v0": round_float(feature_cosine),
                "page_signature_jaccard": round_float(page_jaccard),
                "table_layout_jaccard": round_float(table_layout_jaccard),
                "table_content_jaccard": round_float(table_content_jaccard),
                "result_path": str(result_path),
            }
        )

    pair_result_rows.sort(key=lambda row: row["section_code"])
    write_csv(
        output_dir / "comparison_results_v0.csv",
        pair_result_rows,
        [
            "pair_id",
            "section_code",
            "left_object_id",
            "left_bundle_id",
            "left_crc32",
            "right_object_id",
            "right_bundle_id",
            "right_crc32",
            "weighted_similarity_v0",
            "feature_cosine_v0",
            "page_signature_jaccard",
            "table_layout_jaccard",
            "table_content_jaccard",
            "result_path",
        ],
    )

    by_section = defaultdict(list)
    for row in pair_result_rows:
        by_section[row["section_code"]].append(row["weighted_similarity_v0"])

    summary = {
        "schema_version": "comparison_results_v0_index",
        "generated_at": generated_at,
        "base_dir": str(base_dir),
        "output_dir": str(output_dir),
        "pair_count": len(pair_result_rows),
        "sections": sorted(by_section),
        "files": {
            "comparison_results": "comparison_results_v0.csv",
            "pair_json": "*.json",
        },
    }
    write_json(output_dir / "comparison_results_v0.json", summary)

    readme = f"""# comparison_results_v0

First exploratory same-section comparisons for `element_base_v0`.

Generated at:

- `{generated_at}`

The score is intentionally simple:

- `feature_cosine_v0` - cosine over a compact numeric vector
- `page_signature_jaccard` - multiset overlap of page layout signatures
- `table_layout_jaccard` - multiset overlap of table layout signatures
- `table_content_jaccard` - multiset overlap of hashed table content

`weighted_similarity_v0` is a temporary weighted mix for research only.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=r"E:\repos\DocSpectrum\samples\element_base_v0",
        help="Directory with generated element_base_v0 artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\repos\DocSpectrum\samples\comparison_results_v0",
        help="Directory for generated comparison_result_v0 artifacts.",
    )
    args = parser.parse_args()
    build(Path(args.base_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
