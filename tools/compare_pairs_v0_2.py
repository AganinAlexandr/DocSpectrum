#!/usr/bin/env python3
"""Create comparison_result_v0_2 artifacts with a first text axis.

This is a lexical text baseline, not the final semantic model:

- text segment hashes capture exact repeated normalized text fragments;
- word shingle hashes capture stable phrase-level overlap;
- raw text is never written to result artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


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


STRUCTURAL_AXIS_WEIGHTS = {
    "page_signature_jaccard": 0.40,
    "table_layout_jaccard": 0.35,
    "table_content_jaccard": 0.25,
}

TEXT_AXIS_WEIGHTS = {
    "text_segment_hash_jaccard": 0.35,
    "text_word_shingle_jaccard": 0.65,
}

COMBINED_AXIS_WEIGHTS = {
    "signature_similarity_v0_1": 0.50,
    "text_similarity_v0_2": 0.50,
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


def feature_status_summary(left: dict[str, str], right: dict[str, str]) -> dict[str, int]:
    summary = Counter()
    for feature in NUMERIC_FEATURES:
        left_has = feature in left and left.get(feature) not in ("", None)
        right_has = feature in right and right.get(feature) not in ("", None)
        if not left_has or not right_has:
            summary["missing"] += 1
            continue
        if safe_float(left.get(feature)) == 0.0 and safe_float(right.get(feature)) == 0.0:
            summary["measured_zero"] += 1
        else:
            summary["measured"] += 1
    return dict(summary)


def multiset_jaccard(left: Counter[str], right: Counter[str]) -> tuple[float, str]:
    if not left and not right:
        return 0.0, "not_applicable"
    keys = set(left) | set(right)
    intersection = sum(min(left[key], right[key]) for key in keys)
    union = sum(max(left[key], right[key]) for key in keys)
    value = intersection / union
    return value, "measured_no_overlap" if value == 0.0 else "measured"


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
                "hash": signature,
                "left_count": left[signature],
                "right_count": right[signature],
                "shared_count": min(left[signature], right[signature]),
            }
        )
    shared.sort(key=lambda item: (-item["shared_count"], item["hash"]))
    return shared[:limit]


def weighted_score(
    axis_values: dict[str, dict[str, Any]],
    weights: dict[str, float],
) -> tuple[float, float]:
    weighted_sum = 0.0
    applicable_weight = 0.0
    for axis_name, axis in axis_values.items():
        if axis["status"] not in {"measured", "measured_no_overlap"}:
            continue
        weight = weights[axis_name]
        applicable_weight += weight
        weighted_sum += weight * safe_float(axis["value"])
    if not applicable_weight:
        return 0.0, 0.0
    return weighted_sum / applicable_weight, applicable_weight


def build_text_profile(export_root: Path, object_id: str, bundle_id: str) -> dict[str, Counter[str] | int]:
    path = export_root / object_id / bundle_id / "text_segments.csv"
    if not path.exists():
        return {
            "segment_hashes": Counter(),
            "word_shingle_hashes": Counter(),
            "segment_count": 0,
            "token_count": 0,
            "word_shingle_count": 0,
        }

    rows = read_csv(path)
    segment_hashes: Counter[str] = Counter()
    all_tokens: list[str] = []
    for row in rows:
        normalized = normalize_text(row.get("normalized_text") or row.get("text_value") or "")
        if not normalized:
            continue
        segment_hashes[sha1_text(normalized)] += 1
        all_tokens.extend(text_tokens(normalized))

    shingle_hashes: Counter[str] = Counter(sha1_text(shingle) for shingle in word_shingles(all_tokens))
    return {
        "segment_hashes": segment_hashes,
        "word_shingle_hashes": shingle_hashes,
        "segment_count": len(segment_hashes),
        "token_count": len(all_tokens),
        "word_shingle_count": sum(shingle_hashes.values()),
    }


def combined_score(structural_score: float, text_score: float, text_status: str) -> tuple[float, float]:
    axes = {
        "signature_similarity_v0_1": {"value": structural_score, "status": "measured"},
        "text_similarity_v0_2": {"value": text_score, "status": text_status},
    }
    return weighted_score(axes, COMBINED_AXIS_WEIGHTS)


def build(base_dir: Path, export_root: Path, output_dir: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    features = read_csv(base_dir / "feature_matrix_v0.csv")
    pairs = read_csv(base_dir / "comparison_pairs_v0.csv")
    pages = read_csv(base_dir / "page_signatures_v0.csv")
    tables = read_csv(base_dir / "table_signatures_v0.csv")

    features_by_key = {
        (row["object_id"], row["bundle_id"]): row
        for row in features
    }
    text_profile_cache: dict[tuple[str, str], dict[str, Any]] = {}

    output_dir.mkdir(parents=True, exist_ok=True)
    pair_result_rows = []
    status_counter = Counter()

    for pair in pairs:
        left_key = (pair["left_object_id"], pair["left_bundle_id"])
        right_key = (pair["right_object_id"], pair["right_bundle_id"])
        left = features_by_key[left_key]
        right = features_by_key[right_key]

        feature_cosine = cosine(log_vector(left, NUMERIC_FEATURES), log_vector(right, NUMERIC_FEATURES))
        feature_statuses = feature_status_summary(left, right)

        left_pages = counter_for(pages, *left_key, "page_signature")
        right_pages = counter_for(pages, *right_key, "page_signature")
        page_jaccard, page_status = multiset_jaccard(left_pages, right_pages)

        left_table_layouts = counter_for(tables, *left_key, "layout_signature")
        right_table_layouts = counter_for(tables, *right_key, "layout_signature")
        table_layout_jaccard, table_layout_status = multiset_jaccard(left_table_layouts, right_table_layouts)

        left_table_content = counter_for(tables, *left_key, "content_sha1")
        right_table_content = counter_for(tables, *right_key, "content_sha1")
        table_content_jaccard, table_content_status = multiset_jaccard(left_table_content, right_table_content)

        structural_axes = {
            "page_signature_jaccard": {"value": page_jaccard, "status": page_status},
            "table_layout_jaccard": {"value": table_layout_jaccard, "status": table_layout_status},
            "table_content_jaccard": {"value": table_content_jaccard, "status": table_content_status},
        }
        structural_similarity, structural_applicable_weight = weighted_score(
            structural_axes,
            STRUCTURAL_AXIS_WEIGHTS,
        )

        if left_key not in text_profile_cache:
            text_profile_cache[left_key] = build_text_profile(export_root, *left_key)
        if right_key not in text_profile_cache:
            text_profile_cache[right_key] = build_text_profile(export_root, *right_key)
        left_text = text_profile_cache[left_key]
        right_text = text_profile_cache[right_key]

        segment_jaccard, segment_status = multiset_jaccard(
            left_text["segment_hashes"],
            right_text["segment_hashes"],
        )
        shingle_jaccard, shingle_status = multiset_jaccard(
            left_text["word_shingle_hashes"],
            right_text["word_shingle_hashes"],
        )
        text_axes = {
            "text_segment_hash_jaccard": {"value": segment_jaccard, "status": segment_status},
            "text_word_shingle_jaccard": {"value": shingle_jaccard, "status": shingle_status},
        }
        text_similarity, text_applicable_weight = weighted_score(text_axes, TEXT_AXIS_WEIGHTS)
        text_status = "not_applicable" if not text_applicable_weight else (
            "measured_no_overlap" if text_similarity == 0.0 else "measured"
        )
        combined_similarity, combined_applicable_weight = combined_score(
            structural_similarity,
            text_similarity,
            text_status,
        )

        for axis in {**structural_axes, **text_axes}.values():
            status_counter[axis["status"]] += 1

        result = {
            "schema_version": "comparison_result_v0_2",
            "generated_at": generated_at,
            "pair_id": pair["pair_id"],
            "comparison_mode": pair["comparison_mode"],
            "section_code": pair["section_code"],
            "left": {
                "object_id": left["object_id"],
                "bundle_id": left["bundle_id"],
                "crc32": left["crc32"],
                "file_name": left["file_name"],
                "text_profile": {
                    "segment_count": left_text["segment_count"],
                    "token_count": left_text["token_count"],
                    "word_shingle_count": left_text["word_shingle_count"],
                },
            },
            "right": {
                "object_id": right["object_id"],
                "bundle_id": right["bundle_id"],
                "crc32": right["crc32"],
                "file_name": right["file_name"],
                "text_profile": {
                    "segment_count": right_text["segment_count"],
                    "token_count": right_text["token_count"],
                    "word_shingle_count": right_text["word_shingle_count"],
                },
            },
            "similarity_summary": {
                "combined_similarity_v0_2": round_float(combined_similarity),
                "signature_similarity_v0_1": round_float(structural_similarity),
                "text_similarity_v0_2": round_float(text_similarity),
                "feature_cosine_v0": round_float(feature_cosine),
                "feature_cosine_role": "diagnostic",
                "combined_axes_applicable_weight": round_float(combined_applicable_weight),
                "coverage": {
                    "numeric_features": len(NUMERIC_FEATURES),
                    "numeric_feature_statuses": feature_statuses,
                    "axes": [
                        "signature_similarity_v0_1",
                        "text_similarity_v0_2",
                    ],
                },
            },
            "axis_breakdown": {
                "structural_signatures": {
                    "role": "scoring",
                    "weight": COMBINED_AXIS_WEIGHTS["signature_similarity_v0_1"],
                    "value": round_float(structural_similarity),
                    "applicable_weight": round_float(structural_applicable_weight),
                    "subaxes": {
                        "page_signature_jaccard": {
                            "value": round_float(page_jaccard),
                            "status": page_status,
                            "weight": STRUCTURAL_AXIS_WEIGHTS["page_signature_jaccard"],
                        },
                        "table_layout_jaccard": {
                            "value": round_float(table_layout_jaccard),
                            "status": table_layout_status,
                            "weight": STRUCTURAL_AXIS_WEIGHTS["table_layout_jaccard"],
                        },
                        "table_content_jaccard": {
                            "value": round_float(table_content_jaccard),
                            "status": table_content_status,
                            "weight": STRUCTURAL_AXIS_WEIGHTS["table_content_jaccard"],
                        },
                    },
                },
                "text": {
                    "role": "scoring",
                    "weight": COMBINED_AXIS_WEIGHTS["text_similarity_v0_2"],
                    "value": round_float(text_similarity),
                    "status": text_status,
                    "applicable_weight": round_float(text_applicable_weight),
                    "privacy": "hashes_only_no_raw_text",
                    "subaxes": {
                        "text_segment_hash_jaccard": {
                            "value": round_float(segment_jaccard),
                            "status": segment_status,
                            "weight": TEXT_AXIS_WEIGHTS["text_segment_hash_jaccard"],
                        },
                        "text_word_shingle_jaccard": {
                            "value": round_float(shingle_jaccard),
                            "status": shingle_status,
                            "weight": TEXT_AXIS_WEIGHTS["text_word_shingle_jaccard"],
                        },
                    },
                },
                "feature_cosine": {
                    "role": "diagnostic",
                    "value": round_float(feature_cosine),
                    "numeric_feature_statuses": feature_statuses,
                },
            },
            "shared_hashes": {
                "text_segments_top": top_common(
                    left_text["segment_hashes"],
                    right_text["segment_hashes"],
                ),
                "word_shingles_top": top_common(
                    left_text["word_shingle_hashes"],
                    right_text["word_shingle_hashes"],
                ),
            },
            "v0_2_note": (
                "Text axis is a lexical/phrase-level baseline. It writes only "
                "hashes and counts, not raw text. Embedding or LLM semantic "
                "similarity is intentionally deferred."
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
                "right_object_id": right["object_id"],
                "right_bundle_id": right["bundle_id"],
                "combined_similarity_v0_2": round_float(combined_similarity),
                "signature_similarity_v0_1": round_float(structural_similarity),
                "text_similarity_v0_2": round_float(text_similarity),
                "text_segment_hash_jaccard": round_float(segment_jaccard),
                "text_segment_status": segment_status,
                "text_word_shingle_jaccard": round_float(shingle_jaccard),
                "text_word_shingle_status": shingle_status,
                "feature_cosine_v0": round_float(feature_cosine),
                "feature_cosine_role": "diagnostic",
                "left_text_segment_count": left_text["segment_count"],
                "right_text_segment_count": right_text["segment_count"],
                "left_text_token_count": left_text["token_count"],
                "right_text_token_count": right_text["token_count"],
                "left_word_shingle_count": left_text["word_shingle_count"],
                "right_word_shingle_count": right_text["word_shingle_count"],
                "result_path": str(result_path),
            }
        )

    pair_result_rows.sort(key=lambda row: (row["section_code"], row["pair_id"]))
    write_csv(
        output_dir / "comparison_results_v0_2.csv",
        pair_result_rows,
        [
            "pair_id",
            "section_code",
            "left_object_id",
            "left_bundle_id",
            "right_object_id",
            "right_bundle_id",
            "combined_similarity_v0_2",
            "signature_similarity_v0_1",
            "text_similarity_v0_2",
            "text_segment_hash_jaccard",
            "text_segment_status",
            "text_word_shingle_jaccard",
            "text_word_shingle_status",
            "feature_cosine_v0",
            "feature_cosine_role",
            "left_text_segment_count",
            "right_text_segment_count",
            "left_text_token_count",
            "right_text_token_count",
            "left_word_shingle_count",
            "right_word_shingle_count",
            "result_path",
        ],
    )

    by_section = defaultdict(list)
    text_by_section = defaultdict(list)
    for row in pair_result_rows:
        by_section[row["section_code"]].append(safe_float(row["combined_similarity_v0_2"]))
        text_by_section[row["section_code"]].append(safe_float(row["text_similarity_v0_2"]))

    summary = {
        "schema_version": "comparison_results_v0_2_index",
        "generated_at": generated_at,
        "base_dir": str(base_dir),
        "export_root": str(export_root),
        "output_dir": str(output_dir),
        "pair_count": len(pair_result_rows),
        "sections": sorted(by_section),
        "metric_roles": {
            "combined_similarity_v0_2": "scoring",
            "signature_similarity_v0_1": "scoring_subaxis",
            "text_similarity_v0_2": "scoring_subaxis",
            "feature_cosine_v0": "diagnostic",
        },
        "combined_axis_weights": COMBINED_AXIS_WEIGHTS,
        "text_axis_weights": TEXT_AXIS_WEIGHTS,
        "structural_axis_weights": STRUCTURAL_AXIS_WEIGHTS,
        "axis_status_counts": dict(status_counter),
        "privacy": "text axis stores hashes and counts only; no raw text in artifacts",
        "files": {
            "comparison_results": "comparison_results_v0_2.csv",
            "pair_json": "*.json",
        },
    }
    write_json(output_dir / "comparison_results_v0_2.json", summary)

    readme = f"""# comparison_results_v0_2

First text-axis comparison checkpoint for `DocSpectrum`.

Generated at:

- `{generated_at}`

Inputs:

- element base: `{base_dir}`
- explorer exports: `{export_root}`

Key policy:

- `combined_similarity_v0_2` is the main scoring field.
- `signature_similarity_v0_1` is the structural scoring subaxis.
- `text_similarity_v0_2` is the text scoring subaxis.
- `feature_cosine_v0` remains diagnostic only.
- Text artifacts store hashes and counts only, not raw text.

This is a lexical/phrase baseline before embedding or LLM semantic similarity.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=r"E:\output\DocSpectrum\element_base_v0_18_n2",
        help="Directory with generated element_base_v0 artifacts.",
    )
    parser.add_argument(
        "--export-root",
        default=r"E:\output\DocSpectrum\export",
        help="Root directory with explorer exports.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\output\DocSpectrum\comparison_results_v0_2_18_n2",
        help="Directory for generated comparison_result_v0_2 artifacts.",
    )
    args = parser.parse_args()
    build(Path(args.base_dir), Path(args.export_root), Path(args.output_dir))


if __name__ == "__main__":
    main()
