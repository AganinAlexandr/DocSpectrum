from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

DEFAULT_INPUT_XLSX = Path(r"E:\commons\DocSpectrum\Капремонт_Объекты.xlsx")
DEFAULT_SOURCE_ROOT = Path(r"E:\MSE_арх")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\cross_org_manifest_v0")

TARGET_GROUPS = {"УУиР"}
TARGET_SUBGROUPS = {"УУиР"}
BASELINE_DESIGNER = "РСПК"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cell_column_number(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        raise ValueError(f"Cannot parse cell ref: {cell_ref}")
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - 64
    return number


def read_shared_strings(xlsx: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(xlsx.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings: list[str] = []
    for item in root.findall("a:si", XLSX_NS):
        strings.append("".join(text.text or "" for text in item.findall(".//a:t", XLSX_NS)))
    return strings


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find("a:v", XLSX_NS)
    value = "" if value_node is None else value_node.text or ""
    if cell.get("t") == "s" and value:
        return shared_strings[int(value)].strip()
    if cell.get("t") == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", XLSX_NS)).strip()
    return value.strip()


def read_xlsx_rows(path: Path) -> list[dict[int, str]]:
    with zipfile.ZipFile(path) as xlsx:
        shared_strings = read_shared_strings(xlsx)
        sheet = ET.fromstring(xlsx.read("xl/worksheets/sheet1.xml"))

    rows: list[dict[int, str]] = []
    for row in sheet.findall(".//a:sheetData/a:row", XLSX_NS):
        values: dict[int, str] = {"_row": row.get("r", "")}  # type: ignore[assignment]
        for cell in row.findall("a:c", XLSX_NS):
            values[cell_column_number(cell.get("r", ""))] = cell_value(cell, shared_strings)
        if any(value for key, value in values.items() if key != "_row"):
            rows.append(values)
    return rows


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def find_header_row(rows: list[dict[int, str]]) -> tuple[int, dict[int, str]]:
    required = {"номер", "год", "название", "группа", "подгруппа", "гип", "проектировщик"}
    for index, row in enumerate(rows):
        values = {normalize_header(str(value)) for key, value in row.items() if key != "_row"}
        if required.issubset(values):
            return index, row
    raise ValueError("Cannot find registry header row in xlsx")


def archive_key_from_number(value: str, year: str) -> str:
    digits = re.sub(r"\D+", "", value)
    if len(digits) == 6:
        return f"{digits[:4]}_{digits[4:]}"
    if len(digits) >= 5 and year:
        year_suffix = re.sub(r"\D+", "", year)[-2:]
        if year_suffix and digits.endswith(year_suffix):
            return f"{digits[:-2]}_{year_suffix}"
    return digits


def normalize_address(value: str) -> str:
    value = re.sub(r"\s*\((?:3\.10|3\.11|ОТ|ГВС|ОВ)\)\s*$", "", value.strip(), flags=re.IGNORECASE)
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value)


def index_source_dirs(source_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not source_root.exists():
        return result
    for child in source_root.iterdir():
        if child.is_dir():
            match = re.match(r"(\d{4}_\d{2})\b", child.name)
            if match:
                result.setdefault(match.group(1), child)
    return result


def build_manifest_rows(input_xlsx: Path, source_root: Path) -> list[dict[str, Any]]:
    raw_rows = read_xlsx_rows(input_xlsx)
    header_index, header_row = find_header_row(raw_rows)
    headers = {
        normalize_header(str(value)): column
        for column, value in header_row.items()
        if column != "_row" and str(value).strip()
    }
    source_dirs = index_source_dirs(source_root)
    rows: list[dict[str, Any]] = []
    for raw in raw_rows[header_index + 1:]:
        get = lambda name: str(raw.get(headers[name], "") or "").strip()
        source_number = get("номер")
        year = get("год")
        if not source_number:
            continue
        work_group = get("группа")
        work_subgroup = get("подгруппа")
        if work_group not in TARGET_GROUPS and work_subgroup not in TARGET_SUBGROUPS:
            continue
        designer = get("проектировщик")
        object_id = archive_key_from_number(source_number, year)
        source_dir = source_dirs.get(object_id)
        rows.append(
            {
                "source_row": raw.get("_row", ""),
                "source_number": source_number,
                "year": year,
                "object_id": object_id,
                "address_raw": get("название"),
                "address_normalized": normalize_address(get("название")),
                "work_group": work_group,
                "work_subgroup": work_subgroup,
                "main_group": get("глав_груп") if "глав_груп" in headers else "",
                "archive_status": get("архив") if "архив" in headers else "",
                "gip": get("гип"),
                "designer": designer,
                "contractor": get("генподрядчик") if "генподрядчик" in headers else "",
                "corpus_role": "rpsk_baseline" if designer == BASELINE_DESIGNER else "cross_org_candidate",
                "source_dir_exists": bool(source_dir),
                "source_dir": str(source_dir) if source_dir else "",
            }
        )
    rows.sort(key=lambda row: (row["corpus_role"], row["designer"], row["object_id"], row["source_row"]))
    return rows


def build_designer_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_designer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_designer[str(row["designer"])].append(row)
    summary = []
    for designer, items in sorted(by_designer.items(), key=lambda item: (-len(item[1]), item[0])):
        subgroups = Counter(str(row["work_subgroup"]) for row in items)
        gips = Counter(str(row["gip"]) for row in items)
        summary.append(
            {
                "designer": designer,
                "row_count": len(items),
                "object_count": len({row["object_id"] for row in items}),
                "address_count": len({row["address_normalized"] for row in items}),
                "source_dir_exists_count": sum(1 for row in items if row["source_dir_exists"]),
                "corpus_role": "rpsk_baseline" if designer == BASELINE_DESIGNER else "cross_org_candidate",
                "subgroups": "; ".join(f"{key}:{value}" for key, value in subgroups.most_common()),
                "gips": "; ".join(f"{key}:{value}" for key, value in gips.most_common()),
            }
        )
    return summary


def build_address_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_address[str(row["address_normalized"])].append(row)
    summary = []
    for address, items in sorted(by_address.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(items) < 2:
            continue
        summary.append(
            {
                "address_normalized": address,
                "row_count": len(items),
                "object_ids": "; ".join(str(row["object_id"]) for row in items),
                "designers": "; ".join(sorted({str(row["designer"]) for row in items})),
                "subgroups": "; ".join(str(row["work_subgroup"]) for row in items),
                "corpus_roles": "; ".join(sorted({str(row["corpus_role"]) for row in items})),
            }
        )
    return summary


def build(input_xlsx: Path, source_root: Path, output_dir: Path) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = build_manifest_rows(input_xlsx, source_root)
    designer_summary = build_designer_summary(rows)
    address_summary = build_address_summary(rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_fields = [
        "source_row",
        "source_number",
        "year",
        "object_id",
        "address_raw",
        "address_normalized",
        "work_group",
        "work_subgroup",
        "main_group",
        "archive_status",
        "gip",
        "designer",
        "contractor",
        "corpus_role",
        "source_dir_exists",
        "source_dir",
    ]
    write_csv(output_dir / "cross_org_manifest_v0.csv", rows, manifest_fields)
    write_csv(
        output_dir / "cross_org_designer_summary_v0.csv",
        designer_summary,
        [
            "designer",
            "row_count",
            "object_count",
            "address_count",
            "source_dir_exists_count",
            "corpus_role",
            "subgroups",
            "gips",
        ],
    )
    write_csv(
        output_dir / "cross_org_address_groups_v0.csv",
        address_summary,
        ["address_normalized", "row_count", "object_ids", "designers", "subgroups", "corpus_roles"],
    )

    role_counts = Counter(str(row["corpus_role"]) for row in rows)
    summary = {
        "schema_version": "cross_org_manifest_v0",
        "generated_at": generated_at,
        "input_xlsx": str(input_xlsx),
        "source_root": str(source_root),
        "output_dir": str(output_dir),
        "row_count": len(rows),
        "object_count": len({row["object_id"] for row in rows}),
        "designer_count": len({row["designer"] for row in rows if row["designer"]}),
        "role_counts": dict(role_counts),
        "designer_summary": designer_summary,
        "address_group_count": len(address_summary),
        "modeling_rules": [
            "This manifest is an inventory layer; it does not change scoring.",
            "RSPK rows remain the baseline calibration corpus.",
            "Non-RSPK UUiR rows are cross-org candidates for Axis C and Axis B transfer validation.",
            "Узел учета is a different capital-repair work type and is intentionally excluded from the UUiR manifest.",
            "Small designers with fewer than 5 rows are useful as contrast, not standalone statistics.",
        ],
        "files": {
            "manifest": "cross_org_manifest_v0.csv",
            "designer_summary": "cross_org_designer_summary_v0.csv",
            "address_groups": "cross_org_address_groups_v0.csv",
        },
    }
    write_json(output_dir / "cross_org_manifest_v0.json", summary)

    readme = f"""# cross_org_manifest_v0

Cross-organization UUiR manifest built from the master capital-repair object registry.

Generated at:

- `{generated_at}`

Inputs:

- registry xlsx: `{input_xlsx}`
- source root: `{source_root}`

Key policy:

- This is an inventory/eval planning layer, not a scoring layer.
- `rpsk_baseline` rows preserve the current calibration corpus.
- `cross_org_candidate` rows are candidates for Axis C and cross-org Axis B validation.
- Designers with very small row counts are contrast samples, not standalone statistical groups.
- `Узел учета` is a different work type and is intentionally excluded.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DocSpectrum cross-org UUiR manifest from master xlsx registry.")
    parser.add_argument("--input-xlsx", type=Path, default=DEFAULT_INPUT_XLSX)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    build(args.input_xlsx, args.source_root, args.output_dir)


if __name__ == "__main__":
    main()
