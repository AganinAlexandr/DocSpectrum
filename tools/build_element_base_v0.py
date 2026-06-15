#!/usr/bin/env python3
"""Build the first experimental DocSpectrum element base from explorer exports.

This script intentionally creates a small, explainable v0 dataset. It does not
try to define the final ontology of elements. Its purpose is to make the first
measurement loop reproducible: explorer export -> element_base_v0 ->
section_passport_v0.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


SECTION_ORDER = {
    "АР": 10,
    "КР": 20,
    "ПОКР": 30,
    "ПОС": 35,
    "ИД": 40,
    "ИОС5.1": 50,
    "ИОС5.4.1": 60,
    "ИОС5.5.1": 70,
    "СМ": 80,
    "UNKNOWN": 999,
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


def safe_int(value: Any) -> int:
    try:
        if value in ("", None):
            return 0
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def ratio(numerator: float, denominator: float, digits: int = 4) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, digits)


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def infer_section_code(file_name: str) -> str:
    checks = (
        ("ИОС5.4.1", ("ИОС5.4.1", "ИОС5.4")),
        ("ИОС5.5.1", ("ИОС5.5.1", "ИОС5.5")),
        ("ИОС5.1", ("ИОС5.1",)),
        ("ПОКР", ("ПОКР",)),
        ("ПОС", ("ПОС",)),
        ("АР", ("АР",)),
        ("ИД", ("ИД",)),
        ("СМ", ("СМ",)),
        ("КР", ("КР",)),
    )
    upper_name = file_name.upper()
    for code, markers in checks:
        if any(marker.upper() in upper_name for marker in markers):
            return code
    return "UNKNOWN"


def section_role(section_code: str) -> str:
    if section_code == "СМ":
        return "contrast_control"
    if section_code.startswith("ИОС"):
        return "engineering_core"
    if section_code in {"АР", "КР", "ПОКР", "ПОС"}:
        return "project_section"
    if section_code == "ИД":
        return "non_pp87_but_useful"
    return "unknown"


def page_size_key(page: dict[str, str]) -> str:
    width = round(safe_float(page.get("page_width")), 1)
    height = round(safe_float(page.get("page_height")), 1)
    rotation = safe_int(page.get("rotation"))
    return f"{width}x{height}r{rotation}"


def table_layout_signature(table: dict[str, str]) -> str:
    row_count = safe_int(table.get("row_count"))
    column_count = safe_int(table.get("column_count"))
    cell_count = safe_int(table.get("cell_count"))
    text_count = safe_int(table.get("text_element_count"))
    line_count = safe_int(table.get("line_element_count"))
    frame_count = safe_int(table.get("frame_element_count"))
    width = round(safe_float(table.get("width")), 1)
    height = round(safe_float(table.get("height")), 1)
    return (
        f"rows:{row_count}|cols:{column_count}|cells:{cell_count}|"
        f"text:{text_count}|lines:{line_count}|frames:{frame_count}|"
        f"size:{width}x{height}"
    )


def content_hash_for_table(table_id: str, cells_by_table: dict[str, list[dict[str, str]]]) -> str:
    cells = sorted(
        cells_by_table.get(table_id, []),
        key=lambda row: (safe_int(row.get("row_index")), safe_int(row.get("column_index"))),
    )
    values = []
    for cell in cells:
        text = (cell.get("text_value") or "").strip().lower()
        values.append(f"{cell.get('row_index')}:{cell.get('column_index')}:{text}")
    return sha1_text("\n".join(values)) if values else ""


def page_signature(
    page: dict[str, str],
    group_rows: list[dict[str, str]],
) -> tuple[str, str]:
    group_parts = []
    for row in sorted(group_rows, key=lambda item: item.get("group_id", "")):
        group_id = row.get("group_id", "")
        count = safe_int(row.get("element_count"))
        area = round(safe_float(row.get("bbox_area_total")), 1)
        line_length = round(safe_float(row.get("line_length_total")), 1)
        tables = safe_int(row.get("table_count"))
        cells = safe_int(row.get("cell_count"))
        group_parts.append(f"{group_id}:{count}:{area}:{line_length}:{tables}:{cells}")
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
    return sha1_text(source), source


def count_by(rows: list[dict[str, str]], key: str) -> dict[str, int]:
    return dict(Counter(row.get(key, "") or "UNKNOWN" for row in rows))


def sum_field(rows: list[dict[str, str]], key: str) -> float:
    return sum(safe_float(row.get(key)) for row in rows)


def max_field(rows: list[dict[str, str]], key: str) -> float:
    if not rows:
        return 0.0
    return max(safe_float(row.get(key)) for row in rows)


def collect_bundle(bundle_dir: Path, export_root: Path, generated_at: str) -> dict[str, Any]:
    documents = read_csv(bundle_dir / "documents.csv")
    if not documents:
        raise ValueError(f"No document row in {bundle_dir}")
    document = documents[0]
    file_name = document.get("file_name", "")
    object_id = bundle_dir.parent.name
    bundle_id = bundle_dir.name
    section_code = infer_section_code(file_name)

    pages = read_csv(bundle_dir / "pages.csv")
    elements = read_csv(bundle_dir / "elements.csv")
    group_summary = read_csv(bundle_dir / "group_summary.csv")
    tables = read_csv(bundle_dir / "tables.csv")
    table_cells = read_csv(bundle_dir / "table_cells.csv")
    images = read_csv(bundle_dir / "images.csv")
    text_segments = read_csv(bundle_dir / "text_segments.csv")
    layers = read_csv(bundle_dir / "layers.csv")

    groups_by_page: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in group_summary:
        groups_by_page[row.get("page_id", "")].append(row)

    cells_by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
    for cell in table_cells:
        cells_by_table[cell.get("table_id", "")].append(cell)

    group_counts = count_by(elements, "group_id")
    subtype_counts = count_by(elements, "subtype_id")
    language_counts = count_by(text_segments, "language_code")
    encoding_counts = count_by(elements, "encoding_status")
    page_size_counts = Counter(page_size_key(page) for page in pages)
    table_layout_counts = Counter(table_layout_signature(table) for table in tables)

    total_text_chars = sum(safe_int(row.get("char_count")) for row in text_segments)
    total_text_words = sum(safe_int(row.get("word_count")) for row in text_segments)
    broken_encoding_count = sum(
        safe_int(row.get("broken_encoding_count")) for row in group_summary
    )
    visible_element_count = sum(
        1 for row in elements if (row.get("is_visible") or "").lower() == "true"
    )

    page_rows: list[dict[str, Any]] = []
    page_signature_counts: Counter[str] = Counter()
    for page in sorted(pages, key=lambda row: safe_int(row.get("page_number"))):
        signature_hash, signature_source = page_signature(
            page, groups_by_page.get(page.get("page_id", ""), [])
        )
        page_signature_counts[signature_hash] += 1
        page_rows.append(
            {
                "object_id": object_id,
                "bundle_id": bundle_id,
                "section_code": section_code,
                "crc32": document.get("file_crc32", ""),
                "page_id": page.get("page_id", ""),
                "page_number": safe_int(page.get("page_number")),
                "page_size_key": page_size_key(page),
                "element_count": safe_int(page.get("element_count")),
                "text_count": safe_int(page.get("text_count")),
                "line_count": safe_int(page.get("line_count")),
                "frame_count": safe_int(page.get("frame_count")),
                "image_count": safe_int(page.get("image_count")),
                "table_count": safe_int(page.get("table_count")),
                "page_signature": signature_hash,
                "page_signature_source": signature_source,
            }
        )

    table_rows: list[dict[str, Any]] = []
    for table in sorted(tables, key=lambda row: (safe_int(row.get("page_number")), row.get("table_id", ""))):
        layout_signature = table_layout_signature(table)
        table_rows.append(
            {
                "object_id": object_id,
                "bundle_id": bundle_id,
                "section_code": section_code,
                "crc32": document.get("file_crc32", ""),
                "table_id": table.get("table_id", ""),
                "page_number": safe_int(table.get("page_number")),
                "row_count": safe_int(table.get("row_count")),
                "column_count": safe_int(table.get("column_count")),
                "cell_count": safe_int(table.get("cell_count")),
                "text_element_count": safe_int(table.get("text_element_count")),
                "line_element_count": safe_int(table.get("line_element_count")),
                "frame_element_count": safe_int(table.get("frame_element_count")),
                "bbox_area": round_float(safe_float(table.get("bbox_area")), 2),
                "layout_signature": sha1_text(layout_signature),
                "layout_signature_source": layout_signature,
                "content_sha1": content_hash_for_table(table.get("table_id", ""), cells_by_table),
            }
        )

    feature_vector = {
        "page_count": len(pages),
        "element_count": len(elements),
        "visible_element_count": visible_element_count,
        "text_segment_count": len(text_segments),
        "table_count": len(tables),
        "table_cell_count": len(table_cells),
        "image_count": len(images),
        "layer_count": len(layers),
        "total_text_chars": total_text_chars,
        "total_text_words": total_text_words,
        "broken_encoding_count": broken_encoding_count,
        "elements_per_page": ratio(len(elements), len(pages)),
        "text_segments_per_page": ratio(len(text_segments), len(pages)),
        "tables_per_page": ratio(len(tables), len(pages)),
        "table_cells_per_page": ratio(len(table_cells), len(pages)),
        "images_per_page": ratio(len(images), len(pages)),
        "table_cells_per_table": ratio(len(table_cells), len(tables)),
        "text_segment_ratio": ratio(len(text_segments), len(elements)),
        "image_ratio": ratio(len(images), len(elements)),
        "table_ratio": ratio(len(tables), len(elements)),
        "max_elements_on_page": int(max_field(pages, "element_count")),
        "max_text_segments_on_page": int(max_field(pages, "text_count")),
    }

    for group_id in ("text", "lines", "frames", "images", "tables", "other_vector"):
        feature_vector[f"group_{group_id}_count"] = group_counts.get(group_id, 0)
        feature_vector[f"group_{group_id}_ratio"] = ratio(group_counts.get(group_id, 0), len(elements))

    passport = {
        "schema_version": "section_passport_v0",
        "generated_at": generated_at,
        "source": {
            "export_root": str(export_root),
            "bundle_path": str(bundle_dir),
            "explorer_schema_version": "1.0.0",
        },
        "identity": {
            "object_id": object_id,
            "bundle_id": bundle_id,
            "document_id": document.get("document_id", ""),
            "section_code": section_code,
            "section_role": section_role(section_code),
            "file_name": file_name,
            "crc32": document.get("file_crc32", ""),
        },
        "document": {
            "file_size_bytes": safe_int(document.get("file_size_bytes")),
            "page_count": safe_int(document.get("page_count")),
            "pdf_version": document.get("pdf_version", ""),
            "has_native_layers": document.get("has_native_layers", ""),
            "has_text_layer": document.get("has_text_layer", ""),
            "has_images": document.get("has_images", ""),
            "has_tables": document.get("has_tables", ""),
            "parse_status": document.get("parse_status", ""),
            "parsed_at": document.get("parsed_at", ""),
        },
        "feature_vector_v0": feature_vector,
        "element_spectrum": {
            "group_counts": group_counts,
            "group_ratios": {
                group_id: ratio(count, len(elements)) for group_id, count in sorted(group_counts.items())
            },
            "subtype_counts_top": dict(Counter(subtype_counts).most_common(25)),
            "encoding_counts": encoding_counts,
        },
        "text_spectrum": {
            "segment_count": len(text_segments),
            "total_chars": total_text_chars,
            "total_words": total_text_words,
            "chars_per_segment": ratio(total_text_chars, len(text_segments)),
            "words_per_segment": ratio(total_text_words, len(text_segments)),
            "language_counts": language_counts,
            "normalized_text_sha1": sha1_text(
                "\n".join((row.get("normalized_text") or "").strip().lower() for row in text_segments)
            ),
        },
        "table_spectrum": {
            "table_count": len(tables),
            "cell_count": len(table_cells),
            "layout_signature_counts": dict(table_layout_counts),
            "repeated_layout_signatures": {
                key: value for key, value in table_layout_counts.items() if value > 1
            },
        },
        "page_spectrum": {
            "page_size_counts": dict(page_size_counts),
            "page_signature_counts": dict(page_signature_counts),
            "repeated_page_signatures": {
                key: value for key, value in page_signature_counts.items() if value > 1
            },
        },
        "page_signatures": page_rows,
        "table_signatures": table_rows,
    }

    document_row = {
        "object_id": object_id,
        "bundle_id": bundle_id,
        "section_code": section_code,
        "section_role": section_role(section_code),
        "document_id": document.get("document_id", ""),
        "crc32": document.get("file_crc32", ""),
        "file_name": file_name,
        **feature_vector,
    }

    return {
        "document": document_row,
        "passport": passport,
        "page_rows": page_rows,
        "table_rows": table_rows,
    }


def canonical_bundle_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    parse_status_rank = 0 if str(row.get("parse_status", "")).lower() == "parsed" else 1
    return (
        parse_status_rank,
        safe_int(row.get("broken_encoding_count")),
        -safe_int(row.get("page_count")),
        str(row.get("bundle_id", "")),
    )


def build(export_root: Path, output_dir: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    bundle_dirs = sorted(
        [path for path in export_root.glob("*/*") if path.is_dir() and (path / "documents.csv").exists()],
        key=lambda path: (path.parent.name, path.name),
    )

    collected = [collect_bundle(bundle_dir, export_root, generated_at) for bundle_dir in bundle_dirs]
    collected.sort(
        key=lambda item: (
            item["document"]["object_id"],
            SECTION_ORDER.get(item["document"]["section_code"], 999),
            item["document"]["bundle_id"],
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    passports_dir = output_dir / "section_passports"
    passports_dir.mkdir(parents=True, exist_ok=True)

    document_rows = [item["document"] for item in collected]
    page_rows = [row for item in collected for row in item["page_rows"]]
    table_rows = [row for item in collected for row in item["table_rows"]]

    for item in collected:
        doc = item["document"]
        passport_path = passports_dir / (
            f"{doc['object_id']}__{doc['section_code']}__{doc['bundle_id']}.json"
        )
        write_json(passport_path, item["passport"])
        doc["passport_path"] = str(passport_path)

    document_fields = list(document_rows[0].keys()) if document_rows else []
    write_csv(output_dir / "documents_index.csv", document_rows, document_fields)

    feature_fields = [
        "object_id",
        "bundle_id",
        "section_code",
        "section_role",
        "crc32",
        "file_name",
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
    write_csv(output_dir / "feature_matrix_v0.csv", document_rows, feature_fields)

    page_fields = [
        "object_id",
        "bundle_id",
        "section_code",
        "crc32",
        "page_id",
        "page_number",
        "page_size_key",
        "element_count",
        "text_count",
        "line_count",
        "frame_count",
        "image_count",
        "table_count",
        "page_signature",
        "page_signature_source",
    ]
    write_csv(output_dir / "page_signatures_v0.csv", page_rows, page_fields)

    table_fields = [
        "object_id",
        "bundle_id",
        "section_code",
        "crc32",
        "table_id",
        "page_number",
        "row_count",
        "column_count",
        "cell_count",
        "text_element_count",
        "line_element_count",
        "frame_element_count",
        "bbox_area",
        "layout_signature",
        "layout_signature_source",
        "content_sha1",
    ]
    write_csv(output_dir / "table_signatures_v0.csv", table_rows, table_fields)

    corpus_signature_rows = []
    for signature_type, rows, key in (
        ("page_layout", page_rows, "page_signature"),
        ("table_layout", table_rows, "layout_signature"),
        ("table_content", table_rows, "content_sha1"),
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            signature = row.get(key)
            if signature:
                grouped[str(signature)].append(row)
        for signature, matches in grouped.items():
            if len(matches) < 2:
                continue
            documents = sorted({f"{row['object_id']}:{row['bundle_id']}" for row in matches})
            sections = sorted({str(row["section_code"]) for row in matches})
            objects = sorted({str(row["object_id"]) for row in matches})
            corpus_signature_rows.append(
                {
                    "signature_type": signature_type,
                    "signature": signature,
                    "occurrence_count": len(matches),
                    "document_count": len(documents),
                    "object_count": len(objects),
                    "sections": "|".join(sections),
                    "objects": "|".join(objects),
                    "documents": "|".join(documents),
                }
            )
    corpus_signature_rows.sort(
        key=lambda row: (
            row["signature_type"],
            -safe_int(row["occurrence_count"]),
            row["signature"],
        )
    )
    write_csv(
        output_dir / "corpus_signatures_v0.csv",
        corpus_signature_rows,
        [
            "signature_type",
            "signature",
            "occurrence_count",
            "document_count",
            "object_count",
            "sections",
            "objects",
            "documents",
        ],
    )

    section_counts = Counter(row["section_code"] for row in document_rows)
    observed_sections = [
        section
        for section, _count in sorted(section_counts.items(), key=lambda item: SECTION_ORDER.get(item[0], 999))
        if section != "UNKNOWN"
    ]
    objects = sorted({str(row["object_id"]) for row in document_rows})
    by_object_section: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in document_rows:
        if row["section_code"] != "UNKNOWN":
            by_object_section[(row["object_id"], row["section_code"])].append(row)

    object_section_rows = []
    canonical_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for object_id in objects:
        for section_code in observed_sections:
            rows = sorted(
                by_object_section.get((object_id, section_code), []),
                key=canonical_bundle_sort_key,
            )
            if not rows:
                status = "missing"
            elif len(rows) == 1:
                status = "ok"
                canonical_rows[(object_id, section_code)] = rows[0]
            else:
                status = "duplicate"
                canonical_rows[(object_id, section_code)] = rows[0]
            object_section_rows.append(
                {
                    "object_id": object_id,
                    "section_code": section_code,
                    "section_role": section_role(section_code),
                    "bundle_count": len(rows),
                    "matrix_status": status,
                    "canonical_bundle_id": rows[0]["bundle_id"] if rows else "",
                    "bundle_ids": "|".join(row["bundle_id"] for row in rows),
                    "file_names": "|".join(row["file_name"] for row in rows),
                    "crc32s": "|".join(row["crc32"] for row in rows),
                    "page_counts": "|".join(str(row["page_count"]) for row in rows),
                }
            )

    write_csv(
        output_dir / "object_section_matrix_v0.csv",
        object_section_rows,
        [
            "object_id",
            "section_code",
            "section_role",
            "bundle_count",
            "matrix_status",
            "canonical_bundle_id",
            "bundle_ids",
            "file_names",
            "crc32s",
            "page_counts",
        ],
    )

    pair_rows = []
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (_object_id, _section_code), row in canonical_rows.items():
        by_section[row["section_code"]].append(row)
    for section_code, rows in sorted(by_section.items(), key=lambda item: SECTION_ORDER.get(item[0], 999)):
        if len(rows) < 2:
            continue
        for left, right in combinations(sorted(rows, key=lambda row: row["object_id"]), 2):
            pair_rows.append(
                {
                    "pair_id": f"{section_code}__{left['object_id']}__{right['object_id']}",
                    "section_code": section_code,
                    "left_object_id": left["object_id"],
                    "left_bundle_id": left["bundle_id"],
                    "left_crc32": left["crc32"],
                    "right_object_id": right["object_id"],
                    "right_bundle_id": right["bundle_id"],
                    "right_crc32": right["crc32"],
                    "comparison_mode": "same_section_all_pairs_v0_1",
                }
            )
    write_csv(
        output_dir / "comparison_pairs_v0.csv",
        pair_rows,
        [
            "pair_id",
            "section_code",
            "left_object_id",
            "left_bundle_id",
            "left_crc32",
            "right_object_id",
            "right_bundle_id",
            "right_crc32",
            "comparison_mode",
        ],
    )

    summary = {
        "schema_version": "element_base_v0",
        "generated_at": generated_at,
        "source_export_root": str(export_root),
        "output_dir": str(output_dir),
        "bundle_count": len(document_rows),
        "object_count": len({row["object_id"] for row in document_rows}),
        "section_counts": dict(sorted(section_counts.items(), key=lambda item: SECTION_ORDER.get(item[0], 999))),
        "total_pages": sum(safe_int(row["page_count"]) for row in document_rows),
        "total_elements": sum(safe_int(row["element_count"]) for row in document_rows),
        "total_text_segments": sum(safe_int(row["text_segment_count"]) for row in document_rows),
        "total_tables": sum(safe_int(row["table_count"]) for row in document_rows),
        "total_table_cells": sum(safe_int(row["table_cell_count"]) for row in document_rows),
        "total_images": sum(safe_int(row["image_count"]) for row in document_rows),
        "files": {
            "documents_index": "documents_index.csv",
            "feature_matrix": "feature_matrix_v0.csv",
            "page_signatures": "page_signatures_v0.csv",
            "table_signatures": "table_signatures_v0.csv",
            "corpus_signatures": "corpus_signatures_v0.csv",
            "comparison_pairs": "comparison_pairs_v0.csv",
            "object_section_matrix": "object_section_matrix_v0.csv",
            "section_passports": "section_passports/*.json",
        },
        "object_section_matrix": {
            "observed_sections": observed_sections,
            "missing_count": sum(1 for row in object_section_rows if row["matrix_status"] == "missing"),
            "duplicate_count": sum(1 for row in object_section_rows if row["matrix_status"] == "duplicate"),
        },
        "comparison_pair_count": len(pair_rows),
        "comparison_pair_mode": "same_section_all_pairs_v0_1",
        "v0_interpretation": (
            "Experimental element base for validating the DocSpectrum measurement "
            "approach. It may be rebuilt when a larger corpus suggests better "
            "element groups and features."
        ),
    }
    write_json(output_dir / "element_base_v0.json", summary)

    readme = f"""# element_base_v0

Experimental element base generated from `pdf-structure-explorer` exports.

Source export root:

- `{export_root}`

Generated at:

- `{generated_at}`

Contents:

- `element_base_v0.json` - summary and file manifest
- `documents_index.csv` - one row per section bundle
- `feature_matrix_v0.csv` - compact numeric feature vector per section
- `page_signatures_v0.csv` - page-level layout signatures
- `table_signatures_v0.csv` - table layout/content signatures
- `corpus_signatures_v0.csv` - repeated page/table signatures across the corpus
- `object_section_matrix_v0.csv` - object/section coverage and duplicate diagnostics
- `comparison_pairs_v0.csv` - same-section N>2 pairs over canonical object-section bundles
- `section_passports/*.json` - library-independent section passports v0

This is a research `v0` artifact. It is intended to test whether the
DocSpectrum idea produces explainable measurements before the project has a
large stable library of sections.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--export-root",
        default=r"E:\output\DocSpectrum\export",
        help="Root directory with explorer exports.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\repos\DocSpectrum\samples\element_base_v0",
        help="Directory for generated element_base_v0 artifacts.",
    )
    args = parser.parse_args()
    build(Path(args.export_root), Path(args.output_dir))


if __name__ == "__main__":
    main()
