#!/usr/bin/env python3
"""Build a lightweight Excel snapshot from DocSpectrum analytics CSV files.

The workbook is a static snapshot for quick visual inspection. The refreshable
transport layer is stored separately in analytics/pq/*.pq.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


REPO_ROOT = Path(r"E:\repos\DocSpectrum")
OUTPUT_PATH = REPO_ROOT / "analytics" / "excel" / "DocSpectrum_dynamics_v0.xlsx"

SOURCES = [
    {
        "sheet": "Project_Events",
        "path": REPO_ROOT / "analytics" / "tables" / "project_events.csv",
    },
    {
        "sheet": "Feature_Matrix",
        "path": REPO_ROOT / "samples" / "element_base_v0" / "feature_matrix_v0.csv",
    },
    {
        "sheet": "Comparison_Detailed",
        "path": REPO_ROOT / "samples" / "detailed_comparison_results_v0" / "detailed_comparison_results_v0.csv",
    },
    {
        "sheet": "Comparison_Fast",
        "path": REPO_ROOT / "samples" / "comparison_results_v0" / "comparison_results_v0.csv",
    },
    {
        "sheet": "Corpus_Signatures",
        "path": REPO_ROOT / "samples" / "element_base_v0" / "corpus_signatures_v0.csv",
        "max_rows": 500,
    },
]


def read_csv_rows(path: Path, max_rows: int | None = None) -> list[list[Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = []
        for index, row in enumerate(reader):
            if max_rows is not None and index > max_rows:
                break
            rows.append(row)
        return rows


def is_number(value: str) -> bool:
    if value == "":
        return False
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", value))


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def sheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{column_name(col_index)}{row_index}"
            text = "" if value is None else str(value)
            if row_index > 1 and is_number(text):
                cells.append(f'<c r="{ref}"><v>{text}</v></c>')
            else:
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
                )
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )


def workbook_xml(sheet_names: list[str]) -> str:
    sheets = []
    for index, name in enumerate(sheet_names, start=1):
        sheets.append(
            f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(sheets)}</sheets>'
        '</workbook>'
    )


def workbook_rels_xml(sheet_count: int) -> str:
    rels = []
    for index in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(rels)}'
        '</Relationships>'
    )


def root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )


def content_types_xml(sheet_count: int) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]
    for index in range(1, sheet_count + 1):
        overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'{"".join(overrides)}'
        '</Types>'
    )


def sanitize_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", "_", name)
    return cleaned[:31] or "Sheet"


def build_workbook(output_path: Path) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sheets: list[tuple[str, list[list[Any]]]] = []
    for source in SOURCES:
        rows = read_csv_rows(source["path"], source.get("max_rows"))
        sheets.append((sanitize_sheet_name(source["sheet"]), rows))

    meta_rows = [
        ["key", "value"],
        ["generated_at", generated_at],
        ["repo_root", str(REPO_ROOT)],
        ["note", "Static workbook snapshot; refreshable Power Query layer is in analytics/pq"],
    ]
    sheets.insert(0, ("Readme", meta_rows))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", root_rels_xml())
        archive.writestr("xl/workbook.xml", workbook_xml([name for name, _ in sheets]))
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml(len(sheets)))
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(rows))

    manifest = {
        "generated_at": generated_at,
        "output_path": str(output_path),
        "sheets": [
            {"sheet": name, "row_count": max(0, len(rows) - 1)}
            for name, rows in sheets
        ],
    }
    manifest_path = output_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    manifest = build_workbook(OUTPUT_PATH)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
