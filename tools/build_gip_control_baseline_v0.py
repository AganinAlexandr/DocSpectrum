#!/usr/bin/env python3
"""Build the first wide GIP-control baseline over eligible cells.

v0.1 interpretation refinement:

- style headline = size-invariant composition, not the mixed ratio+composition score
- content headline = word-shingle near overlap, not only exact weighted overlap

The original exact/mixed signals remain in the artifact for diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


DEFAULT_SECTIONS = Path(r"E:\output\DocSpectrum\gip_control_registry_v0\gip_control_sections_v0.csv")
DEFAULT_CELLS = Path(r"E:\output\DocSpectrum\gip_control_registry_v0\gip_control_cells_v0.csv")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_control_baseline_v0_1")
DEFAULT_EXCLUDED_SECTIONS = frozenset({"UNKNOWN", "ПЗ"})

STYLE_RATIO_KEYS = (
    "page_count",
    "elements_per_page",
    "text_per_page",
    "line_per_page",
    "frame_per_page",
    "image_per_page",
    "table_per_page",
    "text_segments_per_page",
    "avg_table_rows",
    "avg_table_cols",
    "avg_table_cells",
)
STYLE_SHARE_KEYS = ("text_share", "line_share", "frame_share", "image_share", "table_share", "other_share")
CONTENT_WEIGHTS = {
    "text_segment": 0.30,
    "text_word_shingle": 0.25,
    "table_cell_text": 0.20,
    "table_layout_signature": 0.10,
    "table_content_signature": 0.15,
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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


EXCLUDED_SECTIONS_CANON = frozenset({"UNKNOWN", "\u041f\u0417"})


def include_section(section_code: str, excluded_sections: set[str]) -> bool:
    return bool(section_code) and section_code not in excluded_sections


def ratio_similarity(left: dict[str, float], right: dict[str, float], keys: tuple[str, ...]) -> float:
    values = []
    for key in keys:
        a = left.get(key, 0.0)
        b = right.get(key, 0.0)
        if a == 0.0 and b == 0.0:
            continue
        values.append(min(a, b) / max(a, b))
    return sum(values) / len(values) if values else 1.0


def composition_similarity(left: dict[str, float], right: dict[str, float], keys: tuple[str, ...]) -> float:
    return sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)


def multiset_jaccard(left: Counter[str], right: Counter[str]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    intersection = sum(min(left[key], right[key]) for key in keys)
    union = sum(max(left[key], right[key]) for key in keys)
    return intersection / union if union else 0.0


def normalize_segment_text(value: str) -> str:
    return normalize_text((value or "").strip())


def table_layout_signature(row: dict[str, str]) -> str:
    width = round(safe_float(row.get("width")), 1)
    height = round(safe_float(row.get("height")), 1)
    return (
        f"rows:{safe_int(row.get('row_count'))}|cols:{safe_int(row.get('column_count'))}|"
        f"cells:{safe_int(row.get('cell_count'))}|text:{safe_int(row.get('text_element_count'))}|"
        f"lines:{safe_int(row.get('line_element_count'))}|frames:{safe_int(row.get('frame_element_count'))}|"
        f"size:{width}x{height}"
    )


def table_content_signature(table_id: str, table_cells: list[dict[str, str]]) -> str:
    cells = sorted(
        (row for row in table_cells if row.get("table_id") == table_id),
        key=lambda row: (safe_int(row.get("row_index")), safe_int(row.get("column_index"))),
    )
    parts = [
        f"{row.get('row_index')}:{row.get('column_index')}:{normalize_segment_text(row.get('text_value', ''))}"
        for row in cells
    ]
    return sha1_text("\n".join(parts)) if parts else ""


def build_profile(bundle_dir: Path) -> dict[str, Any]:
    pages = read_csv(bundle_dir / "pages.csv")
    tables = read_csv(bundle_dir / "tables.csv")
    table_cells = read_csv(bundle_dir / "table_cells.csv")
    text_segments = read_csv(bundle_dir / "text_segments.csv")

    totals = Counter()
    total_elements = 0
    for row in pages:
        elements = safe_int(row.get("element_count"))
        text = safe_int(row.get("text_count"))
        line = safe_int(row.get("line_count"))
        frame = safe_int(row.get("frame_count"))
        image = safe_int(row.get("image_count"))
        table = safe_int(row.get("table_count"))
        known = text + line + frame + image + table
        totals["text_count"] += text
        totals["line_count"] += line
        totals["frame_count"] += frame
        totals["image_count"] += image
        totals["table_count"] += table
        totals["other_count"] += max(0, elements - known)
        total_elements += elements

    text_hashes: Counter[str] = Counter()
    shingle_hashes: Counter[str] = Counter()
    for row in text_segments:
        normalized = normalize_segment_text(row.get("normalized_text") or row.get("text_value") or "")
        if not normalized:
            continue
        text_hashes[sha1_text(normalized)] += 1
        for shingle in word_shingles(text_tokens(normalized), size=5):
            shingle_hashes[sha1_text(shingle)] += 1

    cell_hashes: Counter[str] = Counter()
    for row in table_cells:
        normalized = normalize_segment_text(row.get("text_value", ""))
        if normalized:
            cell_hashes[sha1_text(normalized)] += 1

    layout_hashes: Counter[str] = Counter()
    content_hashes: Counter[str] = Counter()
    row_counts: list[float] = []
    col_counts: list[float] = []
    cell_counts: list[float] = []
    for row in tables:
        layout_hashes[hashlib.sha1(table_layout_signature(row).encode("utf-8")).hexdigest()] += 1
        content = table_content_signature(row.get("table_id", ""), table_cells)
        if content:
            content_hashes[content] += 1
        row_counts.append(float(safe_int(row.get("row_count"))))
        col_counts.append(float(safe_int(row.get("column_count"))))
        cell_counts.append(float(safe_int(row.get("cell_count"))))

    page_count = len(pages)
    component_total = sum(
        totals[key] for key in ("text_count", "line_count", "frame_count", "image_count", "table_count", "other_count")
    )
    style = {
        "page_count": float(page_count),
        "elements_per_page": total_elements / page_count if page_count else 0.0,
        "text_per_page": totals["text_count"] / page_count if page_count else 0.0,
        "line_per_page": totals["line_count"] / page_count if page_count else 0.0,
        "frame_per_page": totals["frame_count"] / page_count if page_count else 0.0,
        "image_per_page": totals["image_count"] / page_count if page_count else 0.0,
        "table_per_page": totals["table_count"] / page_count if page_count else 0.0,
        "text_segments_per_page": len(text_segments) / page_count if page_count else 0.0,
        "avg_table_rows": mean(row_counts),
        "avg_table_cols": mean(col_counts),
        "avg_table_cells": mean(cell_counts),
        "text_share": totals["text_count"] / component_total if component_total else 0.0,
        "line_share": totals["line_count"] / component_total if component_total else 0.0,
        "frame_share": totals["frame_count"] / component_total if component_total else 0.0,
        "image_share": totals["image_count"] / component_total if component_total else 0.0,
        "table_share": totals["table_count"] / component_total if component_total else 0.0,
        "other_share": totals["other_count"] / component_total if component_total else 0.0,
    }
    content = {
        "text_segment": text_hashes,
        "text_word_shingle": shingle_hashes,
        "table_cell_text": cell_hashes,
        "table_layout_signature": layout_hashes,
        "table_content_signature": content_hashes,
    }
    return {"style": style, "content": content}


def style_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[float, float, float]:
    ratio = ratio_similarity(left["style"], right["style"], STYLE_RATIO_KEYS)
    composition = composition_similarity(left["style"], right["style"], STYLE_SHARE_KEYS)
    return 0.7 * ratio + 0.3 * composition, ratio, composition


def content_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[float, dict[str, float]]:
    weighted_sum = 0.0
    applicable_weight = 0.0
    axes: dict[str, float] = {}
    for kind, weight in CONTENT_WEIGHTS.items():
        value = multiset_jaccard(left["content"][kind], right["content"][kind])
        axes[kind] = value
        if left["content"][kind] or right["content"][kind]:
            weighted_sum += weight * value
            applicable_weight += weight
    return (weighted_sum / applicable_weight if applicable_weight else 0.0), axes


def summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    def values(field: str) -> list[float]:
        return [float(row[field]) for row in rows]

    return {
        "style_similarity_median_v0": round_float(median(values("style_similarity_v0"))),
        "style_similarity_mean_v0": round_float(mean(values("style_similarity_v0"))),
        "style_ratio_similarity_median_v0": round_float(median(values("style_ratio_similarity_v0"))),
        "style_ratio_similarity_mean_v0": round_float(mean(values("style_ratio_similarity_v0"))),
        "style_composition_similarity_median_v0": round_float(median(values("style_composition_similarity_v0"))),
        "style_composition_similarity_mean_v0": round_float(mean(values("style_composition_similarity_v0"))),
        "content_similarity_median_v0": round_float(median(values("content_similarity_v0"))),
        "content_similarity_mean_v0": round_float(mean(values("content_similarity_v0"))),
        "text_segment_jaccard_median_v0": round_float(median(values("text_segment_jaccard"))),
        "text_segment_jaccard_mean_v0": round_float(mean(values("text_segment_jaccard"))),
        "text_word_shingle_jaccard_median_v0": round_float(median(values("text_word_shingle_jaccard"))),
        "text_word_shingle_jaccard_mean_v0": round_float(mean(values("text_word_shingle_jaccard"))),
    }


def build(
    sections_path: Path,
    cells_path: Path,
    export_root: Path,
    output_dir: Path,
    excluded_sections: set[str],
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sections = [
        row
        for row in read_csv(sections_path)
        if row.get("authorship_status") == "ready"
        and include_section(row.get("section_code", ""), excluded_sections)
    ]
    cells = [
        row
        for row in read_csv(cells_path)
        if row.get("eligible_for_gip_control") == "True"
        and include_section(row.get("section_code", ""), excluded_sections)
    ]

    sections_by_h1: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    sections_by_h2: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in sections:
        sections_by_h1[(row["effective_org_canonical"], row["work_type_key"], row["section_code"])].append(row)
        sections_by_h2[(row["effective_gip"], row["work_type_key"], row["section_code"])].append(row)

    profile_cache: dict[str, dict[str, Any]] = {}

    def profile_for(bundle_id: str) -> dict[str, Any]:
        if bundle_id not in profile_cache:
            profile_cache[bundle_id] = build_profile(export_root / bundle_id)
        return profile_cache[bundle_id]

    pair_rows: list[dict[str, Any]] = []
    group_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    overall_rows: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for cell in cells:
        kind = cell["cell_kind"]
        if kind == "h1_within_org_diff_gip":
            key = (cell["org_canonical"], cell["work_type_key"], cell["section_code"])
            members = sections_by_h1.get(key, [])
            cell_id = f"h1|{cell['org_canonical']}|{cell['work_type_key']}|{cell['section_code']}"
        else:
            key = (cell["gip"], cell["work_type_key"], cell["section_code"])
            members = sections_by_h2.get(key, [])
            cell_id = f"h2|{cell['gip']}|{cell['work_type_key']}|{cell['section_code']}"

        for left, right in itertools.combinations(sorted(members, key=lambda row: row["object_id"]), 2):
            if kind == "h1_within_org_diff_gip":
                relation = "same_gip" if left["effective_gip"] == right["effective_gip"] else "diff_gip"
            else:
                relation = "same_org" if left["effective_org_canonical"] == right["effective_org_canonical"] else "cross_org"

            left_profile = profile_for(left["bundle_id"])
            right_profile = profile_for(right["bundle_id"])
            style_value, style_ratio, style_composition = style_score(left_profile, right_profile)
            content_value, content_axes = content_score(left_profile, right_profile)

            row = {
                "cell_id": cell_id,
                "cell_kind": kind,
                "relation": relation,
                "section_code": left["section_code"],
                "work_type_key": left["work_type_key"],
                "left_object_id": left["object_id"],
                "right_object_id": right["object_id"],
                "left_bundle_id": left["bundle_id"],
                "right_bundle_id": right["bundle_id"],
                "left_org": left["effective_org_canonical"],
                "right_org": right["effective_org_canonical"],
                "left_gip": left["effective_gip"],
                "right_gip": right["effective_gip"],
                "style_similarity_v0": round_float(style_value),
                "style_ratio_similarity_v0": round_float(style_ratio),
                "style_composition_similarity_v0": round_float(style_composition),
                "style_headline_similarity_v0_1": round_float(style_composition),
                "content_similarity_v0": round_float(content_value),
                "text_segment_jaccard": round_float(content_axes["text_segment"]),
                "text_word_shingle_jaccard": round_float(content_axes["text_word_shingle"]),
                "content_headline_similarity_v0_1": round_float(content_axes["text_word_shingle"]),
                "table_cell_text_jaccard": round_float(content_axes["table_cell_text"]),
                "table_layout_jaccard": round_float(content_axes["table_layout_signature"]),
                "table_content_jaccard": round_float(content_axes["table_content_signature"]),
            }
            pair_rows.append(row)
            group_rows[(cell_id, relation)].append(row)
            overall_rows[(kind, relation, left["section_code"], left["work_type_key"])].append(row)

    pair_rows.sort(key=lambda row: (row["cell_kind"], row["section_code"], row["work_type_key"], row["cell_id"], row["left_object_id"], row["right_object_id"]))

    cell_summary_rows: list[dict[str, Any]] = []
    for (cell_id, relation), rows in sorted(group_rows.items()):
        sample = rows[0]
        metrics = summarize_metrics(rows)
        cell_summary_rows.append(
            {
                "cell_id": cell_id,
                "cell_kind": sample["cell_kind"],
                "relation": relation,
                "section_code": sample["section_code"],
                "work_type_key": sample["work_type_key"],
                "pair_count": len(rows),
                **metrics,
            }
        )

    overall_summary_rows: list[dict[str, Any]] = []
    for (kind, relation, section_code, work_type_key), rows in sorted(overall_rows.items()):
        metrics = summarize_metrics(rows)
        overall_summary_rows.append(
            {
                "cell_kind": kind,
                "relation": relation,
                "section_code": section_code,
                "work_type_key": work_type_key,
                "pair_count": len(rows),
                **metrics,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_control_pairwise_v0.csv",
        pair_rows,
        [
            "cell_id",
            "cell_kind",
            "relation",
            "section_code",
            "work_type_key",
            "left_object_id",
            "right_object_id",
            "left_bundle_id",
            "right_bundle_id",
            "left_org",
            "right_org",
            "left_gip",
            "right_gip",
            "style_similarity_v0",
            "style_ratio_similarity_v0",
            "style_composition_similarity_v0",
            "style_headline_similarity_v0_1",
            "content_similarity_v0",
            "text_segment_jaccard",
            "text_word_shingle_jaccard",
            "content_headline_similarity_v0_1",
            "table_cell_text_jaccard",
            "table_layout_jaccard",
            "table_content_jaccard",
        ],
    )
    write_csv(
        output_dir / "gip_control_cell_summary_v0.csv",
        cell_summary_rows,
        [
            "cell_id",
            "cell_kind",
            "relation",
            "section_code",
            "work_type_key",
            "pair_count",
            "style_similarity_median_v0",
            "style_similarity_mean_v0",
            "style_ratio_similarity_median_v0",
            "style_ratio_similarity_mean_v0",
            "style_composition_similarity_median_v0",
            "style_composition_similarity_mean_v0",
            "content_similarity_median_v0",
            "content_similarity_mean_v0",
            "text_segment_jaccard_median_v0",
            "text_segment_jaccard_mean_v0",
            "text_word_shingle_jaccard_median_v0",
            "text_word_shingle_jaccard_mean_v0",
        ],
    )
    write_csv(
        output_dir / "gip_control_overall_summary_v0.csv",
        overall_summary_rows,
        [
            "cell_kind",
            "relation",
            "section_code",
            "work_type_key",
            "pair_count",
            "style_similarity_median_v0",
            "style_similarity_mean_v0",
            "style_ratio_similarity_median_v0",
            "style_ratio_similarity_mean_v0",
            "style_composition_similarity_median_v0",
            "style_composition_similarity_mean_v0",
            "content_similarity_median_v0",
            "content_similarity_mean_v0",
            "text_segment_jaccard_median_v0",
            "text_segment_jaccard_mean_v0",
            "text_word_shingle_jaccard_median_v0",
            "text_word_shingle_jaccard_mean_v0",
        ],
    )
    summary = {
        "schema_version": "gip_control_baseline_v0_1",
        "generated_at": generated_at,
        "ready_known_section_count": len(sections),
        "eligible_cell_count": len(cells),
        "profile_cache_document_count": len(profile_cache),
        "pair_count": len(pair_rows),
        "cell_summary_count": len(cell_summary_rows),
        "overall_summary_count": len(overall_summary_rows),
        "files": {
            "pairwise": "gip_control_pairwise_v0.csv",
            "cell_summary": "gip_control_cell_summary_v0.csv",
            "overall_summary": "gip_control_overall_summary_v0.csv",
        },
        "excluded_sections": sorted(excluded_sections),
        "interpretation_note": (
            "v0.1 baseline; style headline=size-invariant composition, "
            "content headline=word-shingle near overlap; exact and mixed metrics "
            "remain for diagnostics; provenance residual remains a follow-up refinement"
        ),
    }
    write_json(output_dir / "gip_control_baseline_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the wide GIP-control baseline v0.1.")
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--exclude-section",
        action="append",
        default=list(EXCLUDED_SECTIONS_CANON),
        help="Section code to exclude from GIP-control baseline. Repeatable.",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.sections,
                args.cells,
                args.export_root,
                args.output_dir,
                {value for value in args.exclude_section if value},
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
