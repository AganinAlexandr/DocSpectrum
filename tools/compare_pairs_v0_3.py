#!/usr/bin/env python3
"""Create comparison_result_v0_3 artifacts with corpus DF/IDF weighting.

This layer compares same-section document pairs through the corpus-frequency
entity library. It is intentionally additive: v0.2 remains the lexical baseline,
while v0.3 introduces IDF-weighted entity overlap.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_corpus_frequency_v0 import build_document_entities, load_structural_entities, read_csv, write_csv, write_json


SCORING_ENTITY_WEIGHTS = {
    "text_segment": 0.25,
    "text_word_shingle": 0.35,
    "table_cell_text": 0.15,
    "table_layout_signature": 0.15,
    "table_content_signature": 0.10,
}

DIAGNOSTIC_ENTITY_KINDS = ("page_signature",)


def safe_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


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


def multiset_jaccard(left: Counter[str], right: Counter[str]) -> tuple[float, str]:
    if not left and not right:
        return 0.0, "not_present"
    keys = set(left) | set(right)
    intersection = sum(min(left[key], right[key]) for key in keys)
    union = sum(max(left[key], right[key]) for key in keys)
    value = intersection / union if union else 0.0
    return value, "measured_no_overlap" if value == 0.0 else "measured"


def idf_weighted_jaccard(
    left: Counter[str],
    right: Counter[str],
    idf_by_hash: dict[str, float],
) -> tuple[float, str, float, float]:
    if not left and not right:
        return 0.0, "not_present", 0.0, 0.0
    keys = set(left) | set(right)
    intersection = 0.0
    union = 0.0
    shared_idf = 0.0
    total_idf = 0.0
    for entity_hash in keys:
        weight = idf_by_hash.get(entity_hash, 1.0)
        intersection += min(left[entity_hash], right[entity_hash]) * weight
        union += max(left[entity_hash], right[entity_hash]) * weight
        total_idf += weight
        if entity_hash in left and entity_hash in right:
            shared_idf += weight
    value = intersection / union if union else 0.0
    return value, "measured_no_overlap" if value == 0.0 else "measured", shared_idf, total_idf


def top_shared_idf(
    left: Counter[str],
    right: Counter[str],
    idf_by_hash: dict[str, float],
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = []
    for entity_hash in set(left) & set(right):
        section_idf = idf_by_hash.get(entity_hash, 1.0)
        rows.append(
            {
                "hash": entity_hash,
                "left_count": left[entity_hash],
                "right_count": right[entity_hash],
                "shared_count": min(left[entity_hash], right[entity_hash]),
                "section_idf": round_float(section_idf),
                "shared_weight": round_float(min(left[entity_hash], right[entity_hash]) * section_idf),
            }
        )
    rows.sort(key=lambda row: (-row["shared_weight"], row["hash"]))
    return rows[:limit]


def load_entity_idf(corpus_dir: Path) -> dict[tuple[str, str, str], float]:
    rows = read_csv(corpus_dir / "entity_frequency_v0.csv")
    return {
        (row["section_code"], row["entity_kind"], row["entity_hash"]): safe_float(row["section_idf"])
        for row in rows
    }


def build_entity_idf_index(
    entity_idf: dict[tuple[str, str, str], float],
) -> dict[tuple[str, str], dict[str, float]]:
    """Pre-index IDF by (section, entity kind) for pairwise scoring."""
    index: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for (section_code, entity_kind, entity_hash), idf in entity_idf.items():
        index[(section_code, entity_kind)][entity_hash] = idf
    return index


def load_baseline_v0_2(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["pair_id"]: row for row in read_csv(path)}


def build_document_entity_cache(
    documents: list[dict[str, str]],
    base_dir: Path,
    export_root: Path,
) -> dict[tuple[str, str], dict[str, Counter[str]]]:
    structural_entities = load_structural_entities(base_dir)
    cache: dict[tuple[str, str], dict[str, Counter[str]]] = {}
    for row in documents:
        key = (row["object_id"], row["bundle_id"])
        cache[key] = build_document_entities(export_root, *key, structural_entities)
    return cache


def build(
    base_dir: Path,
    export_root: Path,
    corpus_dir: Path,
    baseline_v0_2_csv: Path,
    output_dir: Path,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    documents = read_csv(base_dir / "documents_index.csv")
    pairs = read_csv(base_dir / "comparison_pairs_v0.csv")
    baseline_v0_2 = load_baseline_v0_2(baseline_v0_2_csv)
    entity_idf = load_entity_idf(corpus_dir)
    entity_idf_index = build_entity_idf_index(entity_idf)
    document_entities = build_document_entity_cache(documents, base_dir, export_root)

    output_dir.mkdir(parents=True, exist_ok=True)
    pair_rows: list[dict[str, Any]] = []
    status_counter = Counter()

    for pair in pairs:
        pair_id = pair["pair_id"]
        section_code = pair["section_code"]
        left_key = (pair["left_object_id"], pair["left_bundle_id"])
        right_key = (pair["right_object_id"], pair["right_bundle_id"])
        left_entities = document_entities[left_key]
        right_entities = document_entities[right_key]

        axis_values: dict[str, dict[str, Any]] = {}
        axis_details: dict[str, dict[str, Any]] = {}
        for entity_kind in SCORING_ENTITY_WEIGHTS:
            idf_by_hash = entity_idf_index.get((section_code, entity_kind), {})
            value, status, shared_idf, total_idf = idf_weighted_jaccard(
                left_entities[entity_kind],
                right_entities[entity_kind],
                idf_by_hash,
            )
            raw_value, raw_status = multiset_jaccard(left_entities[entity_kind], right_entities[entity_kind])
            axis_values[entity_kind] = {"value": value, "status": status}
            axis_details[entity_kind] = {
                "role": "scoring",
                "weight": SCORING_ENTITY_WEIGHTS[entity_kind],
                "idf_weighted_jaccard": round_float(value),
                "raw_multiset_jaccard": round_float(raw_value),
                "status": status,
                "raw_status": raw_status,
                "left_occurrences": sum(left_entities[entity_kind].values()),
                "right_occurrences": sum(right_entities[entity_kind].values()),
                "left_unique": len(left_entities[entity_kind]),
                "right_unique": len(right_entities[entity_kind]),
                "shared_unique": len(set(left_entities[entity_kind]) & set(right_entities[entity_kind])),
                "shared_idf": round_float(shared_idf),
                "total_union_idf": round_float(total_idf),
            }
            status_counter[status] += 1

        idf_similarity, applicable_weight = weighted_score(axis_values, SCORING_ENTITY_WEIGHTS)
        idf_status = "not_present" if not applicable_weight else (
            "measured_no_overlap" if idf_similarity == 0.0 else "measured"
        )

        diagnostic_axes = {}
        for entity_kind in DIAGNOSTIC_ENTITY_KINDS:
            idf_by_hash = entity_idf_index.get((section_code, entity_kind), {})
            value, status, shared_idf, total_idf = idf_weighted_jaccard(
                left_entities[entity_kind],
                right_entities[entity_kind],
                idf_by_hash,
            )
            raw_value, raw_status = multiset_jaccard(left_entities[entity_kind], right_entities[entity_kind])
            diagnostic_axes[entity_kind] = {
                "role": "diagnostic",
                "idf_weighted_jaccard": round_float(value),
                "raw_multiset_jaccard": round_float(raw_value),
                "status": status,
                "raw_status": raw_status,
                "left_occurrences": sum(left_entities[entity_kind].values()),
                "right_occurrences": sum(right_entities[entity_kind].values()),
                "left_unique": len(left_entities[entity_kind]),
                "right_unique": len(right_entities[entity_kind]),
                "shared_unique": len(set(left_entities[entity_kind]) & set(right_entities[entity_kind])),
                "shared_idf": round_float(shared_idf),
                "total_union_idf": round_float(total_idf),
            }

        baseline = baseline_v0_2.get(pair_id, {})
        result_path = output_dir / f"{pair_id}.json"
        result = {
            "schema_version": "comparison_result_v0_3",
            "generated_at": generated_at,
            "pair_id": pair_id,
            "comparison_mode": pair["comparison_mode"],
            "section_code": section_code,
            "left": {
                "object_id": pair["left_object_id"],
                "bundle_id": pair["left_bundle_id"],
                "crc32": pair["left_crc32"],
            },
            "right": {
                "object_id": pair["right_object_id"],
                "bundle_id": pair["right_bundle_id"],
                "crc32": pair["right_crc32"],
            },
            "similarity_summary": {
                "idf_similarity_v0_3": round_float(idf_similarity),
                "idf_similarity_status": idf_status,
                "idf_applicable_weight": round_float(applicable_weight),
                "combined_similarity_v0_2": round_float(safe_float(baseline.get("combined_similarity_v0_2"))),
                "text_similarity_v0_2": round_float(safe_float(baseline.get("text_similarity_v0_2"))),
                "signature_similarity_v0_1": round_float(safe_float(baseline.get("signature_similarity_v0_1"))),
            },
            "axis_breakdown": {
                "corpus_idf_entities": {
                    "role": "scoring",
                    "weights": SCORING_ENTITY_WEIGHTS,
                    "subaxes": axis_details,
                },
                "diagnostic_entities": diagnostic_axes,
            },
            "shared_hashes": {
                "top_shared_by_idf": {
                    entity_kind: top_shared_idf(
                        left_entities[entity_kind],
                        right_entities[entity_kind],
                        entity_idf_index.get((section_code, entity_kind), {}),
                    )
                    for entity_kind in SCORING_ENTITY_WEIGHTS
                }
            },
            "v0_3_note": (
                "Corpus IDF weighted pairwise comparison. page_signature remains "
                "diagnostic until near-match or bucketed signatures are available. "
                "Artifacts store hashes and counts only, not raw text."
            ),
        }
        write_json(result_path, result)

        row = {
            "pair_id": pair_id,
            "section_code": section_code,
            "left_object_id": pair["left_object_id"],
            "left_bundle_id": pair["left_bundle_id"],
            "right_object_id": pair["right_object_id"],
            "right_bundle_id": pair["right_bundle_id"],
            "idf_similarity_v0_3": round_float(idf_similarity),
            "idf_similarity_status": idf_status,
            "idf_applicable_weight": round_float(applicable_weight),
            "combined_similarity_v0_2": round_float(safe_float(baseline.get("combined_similarity_v0_2"))),
            "text_similarity_v0_2": round_float(safe_float(baseline.get("text_similarity_v0_2"))),
            "signature_similarity_v0_1": round_float(safe_float(baseline.get("signature_similarity_v0_1"))),
            "page_signature_idf_jaccard": diagnostic_axes["page_signature"]["idf_weighted_jaccard"],
            "page_signature_role": "diagnostic",
            "result_path": str(result_path),
        }
        for entity_kind in SCORING_ENTITY_WEIGHTS:
            row[f"{entity_kind}_idf_jaccard"] = axis_details[entity_kind]["idf_weighted_jaccard"]
            row[f"{entity_kind}_raw_jaccard"] = axis_details[entity_kind]["raw_multiset_jaccard"]
            row[f"{entity_kind}_status"] = axis_details[entity_kind]["status"]
            row[f"{entity_kind}_shared_unique"] = axis_details[entity_kind]["shared_unique"]
        pair_rows.append(row)

    pair_rows.sort(key=lambda row: (row["section_code"], row["pair_id"]))
    csv_fields = [
        "pair_id",
        "section_code",
        "left_object_id",
        "left_bundle_id",
        "right_object_id",
        "right_bundle_id",
        "idf_similarity_v0_3",
        "idf_similarity_status",
        "idf_applicable_weight",
        "combined_similarity_v0_2",
        "text_similarity_v0_2",
        "signature_similarity_v0_1",
        "page_signature_idf_jaccard",
        "page_signature_role",
    ]
    for entity_kind in SCORING_ENTITY_WEIGHTS:
        csv_fields.extend(
            [
                f"{entity_kind}_idf_jaccard",
                f"{entity_kind}_raw_jaccard",
                f"{entity_kind}_status",
                f"{entity_kind}_shared_unique",
            ]
        )
    csv_fields.append("result_path")
    write_csv(output_dir / "comparison_results_v0_3.csv", pair_rows, csv_fields)

    by_section = defaultdict(list)
    for row in pair_rows:
        by_section[row["section_code"]].append(safe_float(row["idf_similarity_v0_3"]))
    section_medians = {
        section_code: round_float(statistics.median(values))
        for section_code, values in sorted(by_section.items())
        if values
    }
    summary = {
        "schema_version": "comparison_results_v0_3_index",
        "generated_at": generated_at,
        "base_dir": str(base_dir),
        "export_root": str(export_root),
        "corpus_dir": str(corpus_dir),
        "baseline_v0_2_csv": str(baseline_v0_2_csv),
        "output_dir": str(output_dir),
        "pair_count": len(pair_rows),
        "sections": sorted(by_section),
        "metric_roles": {
            "idf_similarity_v0_3": "scoring",
            "combined_similarity_v0_2": "baseline_reference",
            "page_signature_idf_jaccard": "diagnostic",
        },
        "scoring_entity_weights": SCORING_ENTITY_WEIGHTS,
        "diagnostic_entity_kinds": list(DIAGNOSTIC_ENTITY_KINDS),
        "axis_status_counts": dict(status_counter),
        "section_medians_idf_similarity_v0_3": section_medians,
        "privacy": "hashes and counts only; no raw text in artifacts",
        "files": {
            "comparison_results": "comparison_results_v0_3.csv",
            "pair_json": "*.json",
        },
    }
    write_json(output_dir / "comparison_results_v0_3.json", summary)

    readme = f"""# comparison_results_v0_3

Corpus DF/IDF weighted pairwise comparison checkpoint for `DocSpectrum`.

Generated at:

- `{generated_at}`

Inputs:

- element base: `{base_dir}`
- explorer exports: `{export_root}`
- corpus frequency: `{corpus_dir}`
- v0.2 baseline CSV: `{baseline_v0_2_csv}`

Key policy:

- `idf_similarity_v0_3` is the main scoring field.
- `combined_similarity_v0_2` is carried as a baseline reference.
- `page_signature_idf_jaccard` is diagnostic only until near-match/bucketed signatures exist.
- Artifacts store hashes and counts only, not raw text.
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
        "--corpus-dir",
        default=r"E:\output\DocSpectrum\corpus_frequency_v0_18_n2",
        help="Directory with generated corpus_frequency_v0 artifacts.",
    )
    parser.add_argument(
        "--baseline-v0-2-csv",
        default=r"E:\output\DocSpectrum\comparison_results_v0_2_18_n2\comparison_results_v0_2.csv",
        help="CSV with v0.2 comparison results to carry as baseline reference.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\output\DocSpectrum\comparison_results_v0_3_18_n2",
        help="Directory for generated comparison_result_v0_3 artifacts.",
    )
    args = parser.parse_args()
    build(
        Path(args.base_dir),
        Path(args.export_root),
        Path(args.corpus_dir),
        Path(args.baseline_v0_2_csv),
        Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
