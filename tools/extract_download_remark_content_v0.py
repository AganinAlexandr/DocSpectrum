#!/usr/bin/env python3
"""Extract first-round remark content from legacy .doc/.docx files.

The remark column is located by a header containing "Содержание замечани".
Legacy .doc extraction requires local Microsoft Word through pywin32.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from remark_features import feature_row


DEFAULT_DOWNLOADS = Path(r"C:\Users\alexa\Downloads")
DEFAULT_TARGETS = Path(
    r"E:\output\DocSpectrum\expert_quality_remark_recall_v0\source2_targets_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\download_remark_content_v0"
)
OBJECT_RE = re.compile(r"(?<!\d)(\d{3,4})[-_ ]?(\d{2})(?=\D)")
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REMARK_HEADER_PATTERNS = (
    "содержание замечани",
    "замечания экспертизы",
    "замечание экспертизы",
    "текст замечани",
)


def is_remark_header(value: str) -> bool:
    normalized = value.lower().replace("ё", "е")
    return any(pattern in normalized for pattern in REMARK_HEADER_PATTERNS)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_object_id(number: str, year: str) -> str:
    return f"{int(number):04d}_{int(year):02d}"


def section_from_filename(name: str) -> str:
    upper = name.upper()
    if re.search(r"(?<![А-ЯЁA-Z])(?:ПОКР|ПОС)(?![А-ЯЁA-Z])", upper):
        return "ПОС"
    if re.search(r"(?<![А-ЯЁA-Z])КР(?![А-ЯЁA-Z])", upper):
        return "КР"
    return ""


def round_from_filename(name: str) -> int:
    match = re.search(r"зам[._\s-]*(\d+)", name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"замеч\w*[\s№_-]*(\d+)", name, re.IGNORECASE)
    return int(match.group(1)) if match else 1


def index_files(downloads: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for path in sorted(downloads.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".doc", ".docx"}:
            continue
        if not re.search(r"зам", path.name, re.IGNORECASE):
            continue
        match = OBJECT_RE.search(path.name)
        section = section_from_filename(path.name)
        if not match or not section:
            continue
        key = (normalize_object_id(match.group(1), match.group(2)), section)
        index.setdefault(key, []).append(
            {"path": path, "round": round_from_filename(path.name)}
        )
    return index


def choose_file(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            0 if row["round"] == 1 else 1,
            row["round"],
            1 if "принято" in row["path"].name.lower() else 0,
            row["path"].name.lower(),
        ),
    )[0]


def cell_text(cell: Any) -> str:
    return str(cell.Range.Text or "").strip().rstrip("\r\x07").strip()


def extract_word_table(word: Any, path: Path) -> tuple[list[str], dict[str, Any]]:
    document = word.Documents.Open(str(path.resolve()), False, True, False)
    try:
        best: tuple[list[str], dict[str, Any]] | None = None
        for table_index in range(1, document.Tables.Count + 1):
            table = document.Tables.Item(table_index)
            matrix: dict[tuple[int, int], str] = {}
            max_row = 0
            max_col = 0
            for cell_index in range(1, table.Range.Cells.Count + 1):
                cell = table.Range.Cells.Item(cell_index)
                row_index = int(cell.RowIndex)
                column_index = int(cell.ColumnIndex)
                matrix[(row_index, column_index)] = cell_text(cell)
                max_row = max(max_row, row_index)
                max_col = max(max_col, column_index)
            header_hits = [
                (row_index, column_index)
                for (row_index, column_index), value in matrix.items()
                if is_remark_header(value)
            ]
            for header_row, remark_column in header_hits:
                texts = [
                    matrix.get((row_index, remark_column), "").strip()
                    for row_index in range(header_row + 1, max_row + 1)
                ]
                texts = [text for text in texts if text and len(text) >= 4]
                probe = (
                    texts,
                    {
                        "table_index": table_index,
                        "header_row": header_row,
                        "remark_column": remark_column,
                        "table_row_count": max_row,
                        "table_column_count": max_col,
                    },
                )
                if best is None or len(texts) > len(best[0]):
                    best = probe
        return best if best is not None else ([], {"status": "header_not_found"})
    finally:
        document.Close(False)


def docx_cell_text(cell: ET.Element) -> str:
    return "".join(
        node.text or "" for node in cell.iter(f"{{{WORD_NS}}}t")
    ).strip()


def extract_docx_table(path: Path) -> tuple[list[str], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    best: tuple[list[str], dict[str, Any]] | None = None
    for table_index, table in enumerate(root.iter(f"{{{WORD_NS}}}tbl"), 1):
        rows = list(table.findall(f"{{{WORD_NS}}}tr"))
        matrix = [
            [docx_cell_text(cell) for cell in row.findall(f"{{{WORD_NS}}}tc")]
            for row in rows
        ]
        for header_row, values in enumerate(matrix):
            for remark_column, value in enumerate(values):
                if not is_remark_header(value):
                    continue
                texts = [
                    row[remark_column].strip()
                    for row in matrix[header_row + 1 :]
                    if remark_column < len(row) and row[remark_column].strip()
                ]
                probe = (
                    texts,
                    {
                        "table_index": table_index,
                        "header_row": header_row + 1,
                        "remark_column": remark_column + 1,
                        "table_row_count": len(matrix),
                        "table_column_count": max((len(row) for row in matrix), default=0),
                    },
                )
                if best is None or len(texts) > len(best[0]):
                    best = probe
    return best if best is not None else ([], {"status": "header_not_found"})


def build(
    downloads: Path,
    targets_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    targets = read_csv(targets_path)
    file_index = index_files(downloads)
    inventory = []
    remarks = []

    doc_targets = []
    chosen_by_target = {}
    for target in targets:
        key = (target["object_id"], target["section_code"])
        chosen = choose_file(file_index.get(key, []))
        chosen_by_target[key] = chosen
        if chosen and chosen["path"].suffix.lower() == ".doc":
            doc_targets.append(key)

    word = None
    if doc_targets:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

    try:
        for target in targets:
            key = (target["object_id"], target["section_code"])
            chosen = chosen_by_target[key]
            if not chosen:
                inventory.append(
                    {
                        **target,
                        "source_file": "",
                        "round": "",
                        "extract_status": "not_found",
                        "remark_count": 0,
                    }
                )
                continue
            path = chosen["path"]
            try:
                if path.suffix.lower() == ".docx":
                    texts, evidence = extract_docx_table(path)
                else:
                    texts, evidence = extract_word_table(word, path)
                status = "parsed" if texts else evidence.get("status", "parsed_zero")
            except Exception as error:
                texts = []
                evidence = {"error": f"{type(error).__name__}: {error}"}
                status = "parse_error"
            inventory.append(
                {
                    **target,
                    "source_file": str(path),
                    "round": chosen["round"],
                    "extract_status": status,
                    "remark_count": len(texts),
                    "table_index": evidence.get("table_index", ""),
                    "header_row": evidence.get("header_row", ""),
                    "remark_column": evidence.get("remark_column", ""),
                    "error": evidence.get("error", ""),
                }
            )
            for index, text in enumerate(texts, 1):
                remarks.append(
                    {
                        "object_id": target["object_id"],
                        "section_code": target["section_code"],
                        "expert_hash": target.get("expert_hash", ""),
                        "expert_anchor_role": target.get("expert_anchor_role", ""),
                        "source_kind": "downloads_word",
                        "source_file": str(path),
                        "round": chosen["round"],
                        "remark_index": index,
                        **feature_row(text),
                    }
                )
    finally:
        if word is not None:
            word.Quit()

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "download_remark_inventory_v0.csv",
        inventory,
        list(inventory[0]) if inventory else ["object_id", "section_code"],
    )
    remark_fields = list(remarks[0]) if remarks else [
        "object_id", "section_code", "expert_hash", "expert_anchor_role",
        "source_kind", "source_file", "round",
        "remark_index", "remark_hash", "char_count", "word_count",
        "primary_category_v0", "categories_v0", "depth_class_v0",
        "depth_reason_codes_v0",
    ]
    write_csv(output_dir / "download_remark_content_v0.csv", remarks, remark_fields)
    summary = {
        "schema_version": "download_remark_content_v0",
        "target_count": len(targets),
        "found_count": sum(bool(row["source_file"]) for row in inventory),
        "parsed_positive_count": sum(row["remark_count"] > 0 for row in inventory),
        "not_found_count": sum(row["extract_status"] == "not_found" for row in inventory),
        "remark_count": len(remarks),
        "interpretation": "content_source_only; registry_remains_outcome_authority",
    }
    (output_dir / "download_remark_content_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract source-2 Word remark content.")
    parser.add_argument("--downloads", type=Path, default=DEFAULT_DOWNLOADS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(build(args.downloads, args.targets, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
