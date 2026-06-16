#!/usr/bin/env python3
"""Explain pair similarity through localized shared entity hashes.

The output remains hash-only: it records pages, segment/table/cell ids, counts
and corpus-frequency metadata, but does not write raw text.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


DEFAULT_EXPORT_ROOT = Path(r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view")
DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_CORPUS_DIR = Path(r"E:\output\DocSpectrum\corpus_frequency_v0_rpsk35_nk34")
DEFAULT_COMPARISON_DIR = Path(r"E:\output\DocSpectrum\comparison_results_v0_3_rpsk35_nk34")
DEFAULT_TOP_PAIRS_CSV = Path(r"E:\output\DocSpectrum\cross_org_research_v0\cross_org_top_pairs_v0.csv")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\pair_explanations_v0")


ENTITY_KINDS = (
    "text_segment",
    "text_word_shingle",
    "table_cell_text",
    "table_layout_signature",
    "table_content_signature",
    "page_signature",
)


SCORING_ENTITY_KINDS = (
    "text_segment",
    "text_word_shingle",
    "table_cell_text",
    "table_layout_signature",
    "table_content_signature",
)


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def compact_locations(locations: list[dict[str, Any]], limit: int) -> str:
    parts = []
    for location in locations[:limit]:
        entity_kind = location["entity_kind"]
        page = location.get("page_number", "")
        if entity_kind == "text_segment":
            parts.append(f"p{page}:seg={location.get('text_segment_id')}")
        elif entity_kind == "text_word_shingle":
            parts.append(f"p{page}:seg={location.get('text_segment_id')}:sh={location.get('shingle_index')}")
        elif entity_kind == "table_cell_text":
            parts.append(
                f"p{page}:tbl={location.get('table_id')}:cell={location.get('cell_id')}:"
                f"r{location.get('row_index')}c{location.get('column_index')}"
            )
        elif entity_kind in {"table_layout_signature", "table_content_signature"}:
            parts.append(
                f"p{page}:tbl={location.get('table_id')}:"
                f"{location.get('row_count')}x{location.get('column_count')}:cells={location.get('cell_count')}"
            )
        elif entity_kind == "page_signature":
            parts.append(
                f"p{page}:elements={location.get('element_count')}:text={location.get('text_count')}:"
                f"tables={location.get('table_count')}:images={location.get('image_count')}"
            )
    extra = len(locations) - limit
    if extra > 0:
        parts.append(f"+{extra} more")
    return " | ".join(parts)


def entity_frequency_index(corpus_dir: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (row["section_code"], row["entity_kind"], row["entity_hash"]): row
        for row in read_csv(corpus_dir / "entity_frequency_v0.csv")
    }


def structural_location_index(base_dir: Path) -> dict[tuple[str, str], dict[str, dict[str, list[dict[str, Any]]]]]:
    index: dict[tuple[str, str], dict[str, dict[str, list[dict[str, Any]]]]] = defaultdict(
        lambda: {kind: defaultdict(list) for kind in ENTITY_KINDS}
    )
    for row in read_csv(base_dir / "page_signatures_v0.csv"):
        doc_key = (row["object_id"], row["bundle_id"])
        signature = row.get("page_signature")
        if not signature:
            continue
        index[doc_key]["page_signature"][signature].append(
            {
                "entity_kind": "page_signature",
                "page_id": row.get("page_id"),
                "page_number": row.get("page_number"),
                "element_count": row.get("element_count"),
                "text_count": row.get("text_count"),
                "line_count": row.get("line_count"),
                "frame_count": row.get("frame_count"),
                "image_count": row.get("image_count"),
                "table_count": row.get("table_count"),
            }
        )
    for row in read_csv(base_dir / "table_signatures_v0.csv"):
        doc_key = (row["object_id"], row["bundle_id"])
        base_location = {
            "page_number": row.get("page_number"),
            "table_id": row.get("table_id"),
            "row_count": row.get("row_count"),
            "column_count": row.get("column_count"),
            "cell_count": row.get("cell_count"),
            "text_element_count": row.get("text_element_count"),
            "line_element_count": row.get("line_element_count"),
            "frame_element_count": row.get("frame_element_count"),
            "bbox_area": row.get("bbox_area"),
        }
        layout_signature = row.get("layout_signature")
        if layout_signature:
            index[doc_key]["table_layout_signature"][layout_signature].append(
                {"entity_kind": "table_layout_signature", **base_location}
            )
        content_signature = row.get("content_sha1")
        if content_signature:
            index[doc_key]["table_content_signature"][content_signature].append(
                {"entity_kind": "table_content_signature", **base_location}
            )
    return index


def text_location_index(export_root: Path, object_id: str, bundle_id: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = {kind: defaultdict(list) for kind in ENTITY_KINDS}
    text_path = export_root / object_id / bundle_id / "text_segments.csv"
    if text_path.exists():
        for row in read_csv(text_path):
            normalized = normalize_text(row.get("normalized_text") or row.get("text_value") or "")
            if not normalized:
                continue
            base_location = {
                "entity_kind": "text_segment",
                "page_id": row.get("page_id"),
                "page_number": row.get("page_number"),
                "text_segment_id": row.get("text_segment_id"),
                "element_id": row.get("element_id"),
                "char_count": row.get("char_count"),
                "word_count": row.get("word_count"),
                "encoding_status": row.get("encoding_status"),
                "x1": row.get("x1"),
                "y1": row.get("y1"),
                "x2": row.get("x2"),
                "y2": row.get("y2"),
            }
            index["text_segment"][sha1_text(normalized)].append(base_location)
            tokens = text_tokens(normalized)
            for shingle_index, shingle in enumerate(word_shingles(tokens)):
                index["text_word_shingle"][sha1_text(shingle)].append(
                    {
                        **base_location,
                        "entity_kind": "text_word_shingle",
                        "shingle_index": shingle_index,
                    }
                )

    table_cells_path = export_root / object_id / bundle_id / "table_cells.csv"
    if table_cells_path.exists():
        for row in read_csv(table_cells_path):
            normalized = normalize_text(row.get("text_value") or "")
            if not normalized:
                continue
            index["table_cell_text"][sha1_text(normalized)].append(
                {
                    "entity_kind": "table_cell_text",
                    "page_id": row.get("page_id"),
                    "page_number": row.get("page_number"),
                    "table_id": row.get("table_id"),
                    "cell_id": row.get("cell_id"),
                    "row_index": row.get("row_index"),
                    "column_index": row.get("column_index"),
                    "row_span": row.get("row_span"),
                    "column_span": row.get("column_span"),
                    "encoding_status": row.get("encoding_status"),
                    "child_element_count": row.get("child_element_count"),
                }
            )
    return index


def merge_doc_index(
    text_index: dict[str, dict[str, list[dict[str, Any]]]],
    structural_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    merged = {kind: defaultdict(list) for kind in ENTITY_KINDS}
    for source in (text_index, structural_index):
        for entity_kind, by_hash in source.items():
            for entity_hash, locations in by_hash.items():
                merged[entity_kind][entity_hash].extend(locations)
    return merged


def pair_json_paths(
    comparison_dir: Path,
    explicit_pair_ids: list[str],
    explicit_pair_jsons: list[Path],
    top_pairs_csv: Path | None,
    top_pairs_per_section: int,
    sections: set[str],
) -> list[Path]:
    paths: list[Path] = []
    paths.extend(explicit_pair_jsons)
    paths.extend(comparison_dir / f"{pair_id}.json" for pair_id in explicit_pair_ids)
    if top_pairs_csv:
        for row in read_csv(top_pairs_csv):
            if sections and row.get("section_code") not in sections:
                continue
            if safe_int(row.get("section_rank")) <= top_pairs_per_section:
                paths.append(comparison_dir / f"{row['pair_id']}.json")
    unique: list[Path] = []
    seen = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def explain_pair(
    pair_json: Path,
    export_root: Path,
    base_dir: Path,
    frequency: dict[tuple[str, str, str], dict[str, str]],
    structural_index: dict[tuple[str, str], dict[str, dict[str, list[dict[str, Any]]]]],
    per_kind_limit: int,
    location_limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pair = read_json(pair_json)
    pair_id = pair["pair_id"]
    section_code = pair["section_code"]
    left = pair["left"]
    right = pair["right"]
    left_key = (left["object_id"], left["bundle_id"])
    right_key = (right["object_id"], right["bundle_id"])
    left_index = merge_doc_index(
        text_location_index(export_root, *left_key),
        structural_index.get(left_key, {}),
    )
    right_index = merge_doc_index(
        text_location_index(export_root, *right_key),
        structural_index.get(right_key, {}),
    )
    shared_rows: list[dict[str, Any]] = []
    shared_by_kind: dict[str, int] = {}

    for entity_kind in ENTITY_KINDS:
        shared_hashes = sorted(set(left_index[entity_kind]) & set(right_index[entity_kind]))
        candidate_rows = []
        for entity_hash in shared_hashes:
            freq = frequency.get((section_code, entity_kind, entity_hash), {})
            section_idf = safe_float(freq.get("section_idf"), 1.0)
            left_locations = left_index[entity_kind][entity_hash]
            right_locations = right_index[entity_kind][entity_hash]
            shared_count = min(len(left_locations), len(right_locations))
            shared_weight = shared_count * section_idf
            candidate_rows.append(
                {
                    "pair_id": pair_id,
                    "section_code": section_code,
                    "entity_kind": entity_kind,
                    "entity_hash": entity_hash,
                    "shared_weight": round_float(shared_weight),
                    "section_idf": round_float(section_idf),
                    "left_count": len(left_locations),
                    "right_count": len(right_locations),
                    "shared_count": shared_count,
                    "section_df": safe_int(freq.get("section_df")),
                    "section_document_count": safe_int(freq.get("section_document_count")),
                    "section_df_ratio": safe_float(freq.get("section_df_ratio")),
                    "global_df": safe_int(freq.get("global_df")),
                    "global_document_count": safe_int(freq.get("global_document_count")),
                    "global_df_ratio": safe_float(freq.get("global_df_ratio")),
                    "frequency_bucket": freq.get("frequency_bucket", ""),
                    "left_locations": compact_locations(left_locations, location_limit),
                    "right_locations": compact_locations(right_locations, location_limit),
                }
            )
        candidate_rows.sort(key=lambda row: (-row["shared_weight"], row["entity_hash"]))
        shared_by_kind[entity_kind] = len(candidate_rows)
        for rank, row in enumerate(candidate_rows[:per_kind_limit], start=1):
            shared_rows.append({"entity_rank": rank, **row})

    summary = {
        "pair_id": pair_id,
        "section_code": section_code,
        "pair_json": str(pair_json),
        "left_object_id": left["object_id"],
        "left_bundle_id": left["bundle_id"],
        "right_object_id": right["object_id"],
        "right_bundle_id": right["bundle_id"],
        "idf_similarity_v0_3": pair.get("similarity_summary", {}).get("idf_similarity_v0_3"),
        "combined_similarity_v0_2": pair.get("similarity_summary", {}).get("combined_similarity_v0_2"),
        "text_similarity_v0_2": pair.get("similarity_summary", {}).get("text_similarity_v0_2"),
        "signature_similarity_v0_1": pair.get("similarity_summary", {}).get("signature_similarity_v0_1"),
        "shared_entity_kind_counts": shared_by_kind,
    }
    return summary, shared_rows


def build(
    export_root: Path,
    base_dir: Path,
    corpus_dir: Path,
    comparison_dir: Path,
    output_dir: Path,
    pair_ids: list[str],
    pair_jsons: list[Path],
    top_pairs_csv: Path | None,
    top_pairs_per_section: int,
    sections: set[str],
    per_kind_limit: int,
    location_limit: int,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    frequency = entity_frequency_index(corpus_dir)
    structural_index = structural_location_index(base_dir)
    paths = pair_json_paths(comparison_dir, pair_ids, pair_jsons, top_pairs_csv, top_pairs_per_section, sections)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    entity_rows: list[dict[str, Any]] = []
    missing_paths = []

    for path in paths:
        if not path.exists():
            missing_paths.append(str(path))
            continue
        summary, rows = explain_pair(path, export_root, base_dir, frequency, structural_index, per_kind_limit, location_limit)
        summary_rows.append(
            {
                **{key: value for key, value in summary.items() if key != "shared_entity_kind_counts"},
                **{f"shared_{kind}_unique": summary["shared_entity_kind_counts"].get(kind, 0) for kind in ENTITY_KINDS},
            }
        )
        entity_rows.extend(rows)

    write_csv(
        output_dir / "pair_explanation_summary_v0.csv",
        summary_rows,
        [
            "pair_id",
            "section_code",
            "pair_json",
            "left_object_id",
            "left_bundle_id",
            "right_object_id",
            "right_bundle_id",
            "idf_similarity_v0_3",
            "combined_similarity_v0_2",
            "text_similarity_v0_2",
            "signature_similarity_v0_1",
            *[f"shared_{kind}_unique" for kind in ENTITY_KINDS],
        ],
    )
    write_csv(
        output_dir / "pair_shared_entities_v0.csv",
        entity_rows,
        [
            "pair_id",
            "section_code",
            "entity_kind",
            "entity_rank",
            "entity_hash",
            "shared_weight",
            "section_idf",
            "left_count",
            "right_count",
            "shared_count",
            "section_df",
            "section_document_count",
            "section_df_ratio",
            "global_df",
            "global_document_count",
            "global_df_ratio",
            "frequency_bucket",
            "left_locations",
            "right_locations",
        ],
    )
    write_json(
        output_dir / "pair_explanations_v0.json",
        {
            "schema_version": "pair_explanations_v0",
            "generated_at": generated_at,
            "export_root": str(export_root),
            "base_dir": str(base_dir),
            "corpus_dir": str(corpus_dir),
            "comparison_dir": str(comparison_dir),
            "top_pairs_csv": str(top_pairs_csv) if top_pairs_csv else None,
            "pair_count": len(summary_rows),
            "shared_entity_row_count": len(entity_rows),
            "missing_paths": missing_paths,
            "per_kind_limit": per_kind_limit,
            "location_limit": location_limit,
            "summary_csv": str(output_dir / "pair_explanation_summary_v0.csv"),
            "shared_entities_csv": str(output_dir / "pair_shared_entities_v0.csv"),
            "modeling_rules": [
                "This is an explanation layer over existing v0.3 pairwise results.",
                "Raw text is not written; text-derived entities remain hash-only.",
                "Locations identify pages, segments, tables or cells where shared hashes occur.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Explain shared entities for selected pairwise comparison results.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--comparison-dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pair-id", action="append", default=[])
    parser.add_argument("--pair-json", type=Path, action="append", default=[])
    parser.add_argument("--top-pairs-csv", type=Path, default=None)
    parser.add_argument("--top-pairs-per-section", type=int, default=3)
    parser.add_argument("--section", action="append", default=[])
    parser.add_argument("--per-kind-limit", type=int, default=10)
    parser.add_argument("--location-limit", type=int, default=8)
    args = parser.parse_args()
    top_pairs_csv = args.top_pairs_csv
    if top_pairs_csv is None and not args.pair_id and not args.pair_json:
        top_pairs_csv = DEFAULT_TOP_PAIRS_CSV
    build(
        args.export_root,
        args.base_dir,
        args.corpus_dir,
        args.comparison_dir,
        args.output_dir,
        args.pair_id,
        args.pair_json,
        top_pairs_csv,
        args.top_pairs_per_section,
        set(args.section),
        args.per_kind_limit,
        args.location_limit,
    )


if __name__ == "__main__":
    main()
