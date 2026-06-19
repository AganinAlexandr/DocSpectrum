#!/usr/bin/env python3
"""Augment GIP-control pairwise rows with document-level near-match signals."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


DEFAULT_PAIRWISE = Path(r"E:\output\DocSpectrum\gip_control_baseline_v0_1\gip_control_pairwise_v0.csv")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_control_near_match_v0")
GROUPS = ("text", "lines", "frames", "images", "tables", "other_vector")
COUNT_COLUMNS = {
    "text": "text_count",
    "lines": "line_count",
    "frames": "frame_count",
    "images": "image_count",
    "tables": "table_count",
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


def ratio_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    values = []
    for key in left:
        a = left[key]
        b = right[key]
        if a == 0.0 and b == 0.0:
            continue
        values.append(min(a, b) / max(a, b))
    return sum(values) / len(values) if values else 1.0


def composition_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(min(left[key], right[key]) for key in left)


def set_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def page_size_key(page: dict[str, str]) -> str:
    width = round(safe_float(page.get("page_width")), 1)
    height = round(safe_float(page.get("page_height")), 1)
    rotation = safe_int(page.get("rotation"))
    return f"{width}x{height}r{rotation}"


def table_layout_signature(row: dict[str, str]) -> str:
    width = round(safe_float(row.get("width")), 1)
    height = round(safe_float(row.get("height")), 1)
    return (
        f"rows:{safe_int(row.get('row_count'))}|cols:{safe_int(row.get('column_count'))}|"
        f"cells:{safe_int(row.get('cell_count'))}|text:{safe_int(row.get('text_element_count'))}|"
        f"lines:{safe_int(row.get('line_element_count'))}|frames:{safe_int(row.get('frame_element_count'))}|"
        f"size:{width}x{height}"
    )


def normalize_segment_text(value: str) -> str:
    return normalize_text((value or "").strip())


def build_page_signature(page: dict[str, str], group_rows: list[dict[str, str]]) -> str:
    group_parts = []
    for row in sorted(group_rows, key=lambda item: item.get("group_id", "")):
        group_parts.append(
            f"{row.get('group_id','')}:{safe_int(row.get('element_count'))}:"
            f"{round(safe_float(row.get('bbox_area_total')), 1)}:{round(safe_float(row.get('line_length_total')), 1)}:"
            f"{safe_int(row.get('table_count'))}:{safe_int(row.get('cell_count'))}"
        )
    source = "|".join(
        [
            f"size:{page_size_key(page)}",
            f"elements:{safe_int(page.get('element_count'))}",
            f"text:{safe_int(page.get('text_count'))}",
            f"lines:{safe_int(page.get('line_count'))}",
            f"frames:{safe_int(page.get('frame_count'))}",
            f"images:{safe_int(page.get('image_count'))}",
            f"tables:{safe_int(page.get('table_count'))}",
            "groups:" + ";".join(group_parts),
        ]
    )
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


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


def near_match_score(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    count_ratio = ratio_similarity(left["counts"], right["counts"])
    count_composition = composition_similarity(left["count_shares"], right["count_shares"])
    area_ratio = ratio_similarity(left["areas"], right["areas"])
    area_composition = composition_similarity(left["area_shares"], right["area_shares"])
    element_ratio = (
        min(left["element_count"], right["element_count"]) / max(left["element_count"], right["element_count"])
        if max(left["element_count"], right["element_count"]) > 0
        else 1.0
    )
    structural = 0.30 * count_ratio + 0.20 * count_composition + 0.25 * area_ratio + 0.15 * area_composition + 0.10 * element_ratio
    return {
        "page_near_structural_v0_2": structural,
        "count_ratio_similarity": count_ratio,
        "count_composition_similarity": count_composition,
        "area_ratio_similarity": area_ratio,
        "area_composition_similarity": area_composition,
        "element_count_ratio": element_ratio,
    }


def build_document_pages(bundle_dir: Path) -> list[dict[str, Any]]:
    pages = read_csv(bundle_dir / "pages.csv")
    group_summary = read_csv(bundle_dir / "group_summary.csv")
    tables = read_csv(bundle_dir / "tables.csv")
    table_cells = read_csv(bundle_dir / "table_cells.csv")
    text_segments = read_csv(bundle_dir / "text_segments.csv")

    groups_by_page: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in group_summary:
        groups_by_page[safe_int(row.get("page_number"))].append(row)

    tables_by_page: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in tables:
        tables_by_page[safe_int(row.get("page_number"))].append(row)

    cells_by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in table_cells:
        cells_by_table[row.get("table_id", "")].append(row)

    text_by_page: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in text_segments:
        text_by_page[safe_int(row.get("page_number"))].append(row)

    page_profiles: list[dict[str, Any]] = []
    for page in sorted(pages, key=lambda row: safe_int(row.get("page_number"))):
        page_number = safe_int(page.get("page_number"))
        counts = {group: safe_float(page.get(column)) for group, column in COUNT_COLUMNS.items()}
        known_count = sum(safe_int(page.get(column)) for column in COUNT_COLUMNS.values())
        counts["other_vector"] = max(0.0, safe_float(page.get("element_count")) - known_count)

        areas = {group: 0.0 for group in GROUPS}
        for row in groups_by_page.get(page_number, []):
            group_id = row.get("group_id", "")
            if group_id in areas:
                areas[group_id] = safe_float(row.get("bbox_area_total"))

        count_total = sum(counts.values())
        area_total = sum(areas.values())
        text_entities: set[str] = set()
        shingle_entities: set[str] = set()
        for row in text_by_page.get(page_number, []):
            normalized = normalize_segment_text(row.get("normalized_text") or row.get("text_value") or "")
            if not normalized:
                continue
            text_entities.add(sha1_text(normalized))
            for shingle in word_shingles(text_tokens(normalized), size=5):
                shingle_entities.add(sha1_text(shingle))

        table_layout_entities: set[str] = set()
        table_content_entities: set[str] = set()
        for row in tables_by_page.get(page_number, []):
            table_layout_entities.add(hashlib.sha1(table_layout_signature(row).encode("utf-8")).hexdigest())
            content = table_content_signature(row.get("table_id", ""), cells_by_table.get(row.get("table_id", ""), []))
            if content:
                table_content_entities.add(content)

        page_profiles.append(
            {
                "page_number": page_number,
                "page_signature": build_page_signature(page, groups_by_page.get(page_number, [])),
                "page_size_key": page_size_key(page),
                "element_count": safe_float(page.get("element_count")),
                "counts": counts,
                "count_shares": {group: counts[group] / count_total if count_total else 0.0 for group in GROUPS},
                "areas": areas,
                "area_shares": {group: areas[group] / area_total if area_total else 0.0 for group in GROUPS},
                "text_segment": text_entities,
                "text_word_shingle": shingle_entities,
                "table_layout": table_layout_entities,
                "table_content": table_content_entities,
            }
        )
    return page_profiles


def pair_content_metrics(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_exact_signature_match_v0_2": left["page_signature"] == right["page_signature"],
        "page_text_segment_jaccard_v0_2": set_jaccard(left["text_segment"], right["text_segment"]),
        "page_text_word_shingle_jaccard_v0_2": set_jaccard(left["text_word_shingle"], right["text_word_shingle"]),
        "page_table_layout_jaccard_v0_2": set_jaccard(left["table_layout"], right["table_layout"]),
        "page_table_content_jaccard_v0_2": set_jaccard(left["table_content"], right["table_content"]),
    }


def choose_better(candidate: dict[str, Any] | None, contender: dict[str, Any]) -> dict[str, Any]:
    if candidate is None:
        return contender
    contender_key = (
        contender["page_near_structural_v0_2"],
        contender["page_text_word_shingle_jaccard_v0_2"],
        contender["page_text_segment_jaccard_v0_2"],
        1 if contender["page_exact_signature_match_v0_2"] else 0,
    )
    candidate_key = (
        candidate["page_near_structural_v0_2"],
        candidate["page_text_word_shingle_jaccard_v0_2"],
        candidate["page_text_segment_jaccard_v0_2"],
        1 if candidate["page_exact_signature_match_v0_2"] else 0,
    )
    return contender if contender_key > candidate_key else candidate


def best_directional_matches(
    left_pages: list[dict[str, Any]],
    right_pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for left in left_pages:
        best: dict[str, Any] | None = None
        for right in right_pages:
            row = {**near_match_score(left, right), **pair_content_metrics(left, right)}
            row["left_page_number"] = left["page_number"]
            row["right_page_number"] = right["page_number"]
            best = choose_better(best, row)
        if best is not None:
            matches.append(best)
    return matches


def summarize_matches(matches_lr: list[dict[str, Any]], matches_rl: list[dict[str, Any]]) -> dict[str, Any]:
    rows = matches_lr + matches_rl
    structural = [float(row["page_near_structural_v0_2"]) for row in rows]
    text_shingle = [float(row["page_text_word_shingle_jaccard_v0_2"]) for row in rows]
    text_segment = [float(row["page_text_segment_jaccard_v0_2"]) for row in rows]
    table_layout = [float(row["page_table_layout_jaccard_v0_2"]) for row in rows]
    table_content = [float(row["page_table_content_jaccard_v0_2"]) for row in rows]
    exact = [1.0 if row["page_exact_signature_match_v0_2"] else 0.0 for row in rows]
    strong = [1.0 if float(row["page_near_structural_v0_2"]) >= 0.85 else 0.0 for row in rows]
    moderate = [1.0 if float(row["page_near_structural_v0_2"]) >= 0.70 else 0.0 for row in rows]
    return {
        "page_near_similarity_mean_v0_2": round_float(mean(structural)),
        "page_near_similarity_median_v0_2": round_float(median(structural)),
        "page_near_shingle_mean_v0_2": round_float(mean(text_shingle)),
        "page_near_shingle_median_v0_2": round_float(median(text_shingle)),
        "page_near_text_segment_mean_v0_2": round_float(mean(text_segment)),
        "page_near_text_segment_median_v0_2": round_float(median(text_segment)),
        "page_near_table_layout_mean_v0_2": round_float(mean(table_layout)),
        "page_near_table_content_mean_v0_2": round_float(mean(table_content)),
        "page_near_exact_share_v0_2": round_float(mean(exact)),
        "page_near_strong_share_v0_2": round_float(mean(strong)),
        "page_near_moderate_share_v0_2": round_float(mean(moderate)),
        "page_bidirectional_match_count_v0_2": len(rows),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, float]:
    def values(field: str) -> list[float]:
        return [float(row[field]) for row in rows]

    return {
        "page_near_similarity_median_v0_2": round_float(median(values("page_near_similarity_mean_v0_2"))),
        "page_near_similarity_mean_v0_2": round_float(mean(values("page_near_similarity_mean_v0_2"))),
        "page_near_shingle_median_v0_2": round_float(median(values("page_near_shingle_mean_v0_2"))),
        "page_near_shingle_mean_v0_2": round_float(mean(values("page_near_shingle_mean_v0_2"))),
        "page_near_exact_share_median_v0_2": round_float(median(values("page_near_exact_share_v0_2"))),
        "page_near_strong_share_median_v0_2": round_float(median(values("page_near_strong_share_v0_2"))),
    }


def build(pairwise_path: Path, export_root: Path, output_dir: Path) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pair_rows = read_csv(pairwise_path)

    doc_cache: dict[str, list[dict[str, Any]]] = {}

    def pages_for(bundle_id: str) -> list[dict[str, Any]]:
        if bundle_id not in doc_cache:
            doc_cache[bundle_id] = build_document_pages(export_root / bundle_id)
        return doc_cache[bundle_id]

    enriched_rows: list[dict[str, Any]] = []
    page_match_rows: list[dict[str, Any]] = []
    relation_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in pair_rows:
        left_pages = pages_for(row["left_bundle_id"])
        right_pages = pages_for(row["right_bundle_id"])
        matches_lr = best_directional_matches(left_pages, right_pages)
        matches_rl = best_directional_matches(right_pages, left_pages)
        summary = summarize_matches(matches_lr, matches_rl)
        enriched = {**row, **summary}
        enriched_rows.append(enriched)
        relation_groups[(row["cell_kind"], row["relation"], row["section_code"], row["work_type_key"])].append(enriched)

        pair_id = "|".join((row["left_bundle_id"], row["right_bundle_id"]))
        for direction, matches in (("left_to_right", matches_lr), ("right_to_left", matches_rl)):
            for match in matches:
                page_match_rows.append(
                    {
                        "pair_id": pair_id,
                        "cell_kind": row["cell_kind"],
                        "relation": row["relation"],
                        "section_code": row["section_code"],
                        "work_type_key": row["work_type_key"],
                        "left_bundle_id": row["left_bundle_id"] if direction == "left_to_right" else row["right_bundle_id"],
                        "right_bundle_id": row["right_bundle_id"] if direction == "left_to_right" else row["left_bundle_id"],
                        "direction": direction,
                        **match,
                    }
                )

    enriched_rows.sort(key=lambda row: (row["cell_kind"], row["section_code"], row["work_type_key"], row["left_object_id"], row["right_object_id"]))
    page_match_rows.sort(key=lambda row: (row["cell_kind"], row["section_code"], row["work_type_key"], row["pair_id"], row["direction"], safe_int(row["left_page_number"])))

    summary_rows: list[dict[str, Any]] = []
    for (cell_kind, relation, section_code, work_type_key), rows in sorted(relation_groups.items()):
        summary_rows.append(
            {
                "cell_kind": cell_kind,
                "relation": relation,
                "section_code": section_code,
                "work_type_key": work_type_key,
                "pair_count": len(rows),
                **summarize_group(rows),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_control_pairwise_near_v0.csv",
        enriched_rows,
        list(enriched_rows[0]),
    )
    write_csv(
        output_dir / "gip_control_page_best_matches_v0.csv",
        page_match_rows,
        list(page_match_rows[0]),
    )
    write_csv(
        output_dir / "gip_control_near_summary_v0.csv",
        summary_rows,
        [
            "cell_kind",
            "relation",
            "section_code",
            "work_type_key",
            "pair_count",
            "page_near_similarity_median_v0_2",
            "page_near_similarity_mean_v0_2",
            "page_near_shingle_median_v0_2",
            "page_near_shingle_mean_v0_2",
            "page_near_exact_share_median_v0_2",
            "page_near_strong_share_median_v0_2",
        ],
    )
    summary = {
        "schema_version": "gip_control_near_match_v0",
        "generated_at": generated_at,
        "pairwise_input_count": len(pair_rows),
        "document_profile_count": len(doc_cache),
        "enriched_pair_count": len(enriched_rows),
        "page_best_match_row_count": len(page_match_rows),
        "summary_row_count": len(summary_rows),
        "files": {
            "pairwise_near": "gip_control_pairwise_near_v0.csv",
            "page_best_matches": "gip_control_page_best_matches_v0.csv",
            "summary": "gip_control_near_summary_v0.csv",
        },
        "interpretation_note": (
            "Document-level near-match over best bidirectional page matches; "
            "headline structural near uses page-count/area relaxation, "
            "headline content near uses page-level text shingle overlap."
        ),
    }
    write_json(output_dir / "gip_control_near_match_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GIP-control near-match augmentation v0.")
    parser.add_argument("--pairwise", type=Path, default=DEFAULT_PAIRWISE)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.pairwise, args.export_root, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
