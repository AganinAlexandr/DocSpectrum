from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


DEFAULT_INPUT_XLSX = Path(r"E:\commons\DocSpectrum\Капремонт_дома_УУиР_Подольск.xlsx")
DEFAULT_SOURCE_ROOT = Path(r"E:\MSE_арх")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\object_registry_v0")
DEFAULT_MINSTROY_ROOT = Path(r"E:\Projects\Minstroy")

TEI_CANONICAL_NAMES = {
    "количество подъездов": "entrances_count",
    "количество этажей": "floors_count",
    "общее количество квартир": "apartments_count",
    "длина": "length_m",
    "длина здания": "length_m",
    "длина дома": "length_m",
    "ширина": "width_m",
    "ширина здания": "width_m",
    "ширина дома": "width_m",
    "высота здания": "height_m",
    "высота дома": "height_m",
    "общая высота здания": "height_m",
    "общая высота дома": "height_m",
    "площадь застройки": "footprint_area_m2",
    "строительный объём": "building_volume_m3",
    "общий строительный объём": "building_volume_m3",
    "площадь здания": "total_area_m2",
    "общая площадь": "total_area_m2",
    "общая площадь здания": "total_area_m2",
    "год постройки": "build_year",
}

TEI_CANONICAL_FIELDS = [
    "entrances_count",
    "floors_count",
    "apartments_count",
    "length_m",
    "width_m",
    "height_m",
    "footprint_area_m2",
    "building_volume_m3",
    "total_area_m2",
    "build_year",
]


@dataclass(frozen=True)
class RegistryRow:
    source_number: str
    object_id: str
    address: str
    group: str
    subgroup: str


def archive_key_from_number(value: str) -> str:
    digits = re.sub(r"\D+", "", value)
    if len(digits) == 6:
        return f"{digits[:4]}_{digits[4:]}"
    return digits


def normalize_address(value: str) -> str:
    value = re.sub(r"\s*\((?:3\.10|3\.11)\)\s*$", "", value.strip())
    return re.sub(r"\s+", " ", value)


def parse_decimal(value: str) -> float | None:
    value = value.strip().replace(" ", "").replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def canonical_tei_name(name: str) -> str:
    return TEI_CANONICAL_NAMES.get(name.strip().lower(), "")


def find_default_okei_xsd(root: Path) -> Path | None:
    if not root.exists():
        return None
    return next(root.rglob("explanatorynote-01-06.xsd"), None)


def parse_okei_units(xsd_path: Path | None) -> dict[str, dict[str, str]]:
    if xsd_path is None or not xsd_path.exists():
        return {}
    ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
    root = ET.parse(xsd_path).getroot()
    units: dict[str, dict[str, str]] = {}
    for enum in root.findall('.//xs:simpleType[@name="tOKEI"]//xs:enumeration', ns):
        code = enum.get("value", "")
        if not code:
            continue
        unit = {"unit_name": "", "unit_symbol": ""}
        for doc in enum.findall(".//xs:documentation", ns):
            doc_id = doc.get("{http://www.w3.org/XML/1998/namespace}id") or doc.get("id") or ""
            text = "".join(doc.itertext()).strip()
            if doc_id == "Name":
                unit["unit_name"] = text
            elif doc_id == "Symbol":
                unit["unit_symbol"] = text
        units[code] = unit
    return units


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


def read_registry_xlsx(path: Path) -> list[RegistryRow]:
    with zipfile.ZipFile(path) as xlsx:
        shared_strings = read_shared_strings(xlsx)
        sheet = ET.fromstring(xlsx.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str]] = []
    for row in sheet.findall(".//a:sheetData/a:row", XLSX_NS):
        values: dict[int, str] = {}
        for cell in row.findall("a:c", XLSX_NS):
            value_node = cell.find("a:v", XLSX_NS)
            value = "" if value_node is None else value_node.text or ""
            if cell.get("t") == "s" and value:
                value = shared_strings[int(value)]
            values[cell_column_number(cell.get("r", ""))] = value.strip()
        if values:
            rows.append([values.get(idx, "") for idx in range(1, max(values) + 1)])

    if not rows:
        return []

    headers = [header.strip().lower() for header in rows[0]]
    required = {"номер", "название", "группа", "подгруппа"}
    missing = required - set(headers)
    if missing:
        raise ValueError(f"Missing required xlsx columns: {sorted(missing)}")

    index = {name: headers.index(name) for name in required}
    result: list[RegistryRow] = []
    for row in rows[1:]:
        get = lambda name: row[index[name]].strip() if index[name] < len(row) else ""
        source_number = get("номер")
        if not source_number:
            continue
        result.append(
            RegistryRow(
                source_number=source_number,
                object_id=archive_key_from_number(source_number),
                address=get("название"),
                group=get("группа"),
                subgroup=get("подгруппа"),
            )
        )
    return result


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


def find_explanatory_note_xml(source_dir: Path | None) -> Path | None:
    if source_dir is None or not source_dir.exists():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in source_dir.rglob("*.xml"):
        name = path.name.lower()
        score = 0
        if "пояснительная записка" in name or "раздел пд №1" in name:
            score += 100
        if "раздел пд" in name:
            score += 50
        if "пз" in name or "пзхмл" in name:
            score += 50
        if "№1" in name or "№ 1" in name or "n 1" in name:
            score += 25
        # Some source files have noisy suffixes like "ИУЛ"; TEI content is the
        # strongest signal that this XML is usable as the explanatory note.
        try:
            if b"<TEI>" in path.read_bytes():
                score += 1000
        except OSError:
            pass
        if score:
            candidates.append((score, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1].parts), len(item[1].name), str(item[1]).lower()))
    return candidates[0][1]


def read_tei(
    xml_path: Path | None,
    okei_units: dict[str, dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    if xml_path is None:
        return {}, []
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        return {}, []

    tei_long: list[dict[str, str]] = []
    tei_wide: dict[str, str] = {}
    for item in root.iter("TEI"):
        fields = {child.tag: (child.text or "").strip() for child in list(item)}
        name = fields.get("Name", "")
        value = fields.get("Value", "")
        if not name:
            continue
        measure_code = fields.get("Measure", "")
        unit = okei_units.get(measure_code, {})
        parsed_value = parse_decimal(value)
        tei_long.append(
            {
                "tei_name": name,
                "measure_code": measure_code,
                "unit_name": unit.get("unit_name", ""),
                "unit_symbol": unit.get("unit_symbol", ""),
                "value_raw": value,
                "value_number": "" if parsed_value is None else str(parsed_value),
            }
        )
        tei_wide[name] = value
    return tei_wide, tei_long


def find_project_doc_dir(source_dir: Path | None, subgroup: str) -> Path | None:
    if source_dir is None or not source_dir.exists():
        return None
    subgroup_aliases = {
        "ОВ": (" ов", " от", "ов", "от"),
        "ОТ": (" от", "от"),
        "ГВС": (" гвс", "гвс"),
    }
    aliases = subgroup_aliases.get(subgroup.upper(), (subgroup.lower(),))
    candidates: list[Path] = []
    for path in source_dir.rglob("*"):
        if not path.is_dir():
            continue
        lower_name = path.name.lower()
        if lower_name.startswith("пд ") and any(alias in lower_name for alias in aliases):
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (len(item.parts), len(item.name), str(item).lower()))
    return candidates[0]


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DocSpectrum object registry v0 from Excel and TEI XML.")
    parser.add_argument("--input-xlsx", type=Path, default=DEFAULT_INPUT_XLSX)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--minstroy-root", type=Path, default=DEFAULT_MINSTROY_ROOT)
    parser.add_argument("--okei-xsd", type=Path, default=None)
    args = parser.parse_args()

    registry = read_registry_xlsx(args.input_xlsx)
    source_dirs = index_source_dirs(args.source_root)
    okei_xsd = args.okei_xsd or find_default_okei_xsd(args.minstroy_root)
    okei_units = parse_okei_units(okei_xsd)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tei_names: list[str] = []
    object_rows: list[dict[str, object]] = []
    tei_long_rows: list[dict[str, object]] = []

    for row in registry:
        source_dir = source_dirs.get(row.object_id)
        xml_path = find_explanatory_note_xml(source_dir)
        project_doc_dir = find_project_doc_dir(source_dir, row.subgroup)
        tei_wide, tei_long = read_tei(xml_path, okei_units)
        tei_canonical: dict[str, str] = {}
        for tei in tei_long:
            canonical_name = canonical_tei_name(str(tei["tei_name"]))
            if not canonical_name:
                continue
            tei["canonical_name"] = canonical_name
            tei_canonical.setdefault(canonical_name, str(tei["value_number"] or tei["value_raw"]))
        for name in tei_wide:
            if name not in tei_names:
                tei_names.append(name)
        for tei in tei_long:
            tei_long_rows.append({"object_id": row.object_id, **tei})

        if source_dir is None:
            registry_status = "missing_source_dir"
        elif xml_path is None:
            registry_status = "missing_xml"
        elif not tei_long:
            registry_status = "xml_found_no_tei"
        else:
            registry_status = "ok"

        object_record = {
            "object_id": row.object_id,
            "source_number": row.source_number,
            "address": row.address,
            "address_normalized": normalize_address(row.address),
            "project_group": row.group,
            "project_subgroup": row.subgroup,
            "source_pd_dir": "" if source_dir is None else str(source_dir),
            "project_doc_dir": "" if project_doc_dir is None else str(project_doc_dir),
            "explanatory_note_xml": "" if xml_path is None else str(xml_path),
            "tei_count": len(tei_long),
            "registry_status": registry_status,
        }
        object_record.update({f"tei_norm_{name}": tei_canonical.get(name, "") for name in TEI_CANONICAL_FIELDS})
        object_record.update({f"tei_{name}": tei_wide.get(name, "") for name in tei_names})
        object_rows.append(object_record)

    # Keep columns stable after all TEI names are known.
    base_fields = [
        "object_id",
        "source_number",
        "address",
        "address_normalized",
        "project_group",
        "project_subgroup",
        "source_pd_dir",
        "project_doc_dir",
        "explanatory_note_xml",
        "tei_count",
        "registry_status",
    ]
    normalized_fields = [f"tei_norm_{name}" for name in TEI_CANONICAL_FIELDS]
    wide_fields = base_fields + normalized_fields + [f"tei_{name}" for name in tei_names]
    object_rows = [{field: row.get(field, "") for field in wide_fields} for row in object_rows]

    write_csv(args.output_dir / "object_registry_v0.csv", object_rows, wide_fields)
    write_csv(
        args.output_dir / "object_tei_long_v0.csv",
        tei_long_rows,
        [
            "object_id",
            "tei_name",
            "canonical_name",
            "measure_code",
            "unit_name",
            "unit_symbol",
            "value_raw",
            "value_number",
        ],
    )
    with (args.output_dir / "object_registry_v0.jsonl").open("w", encoding="utf-8") as file:
        for row in object_rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_xlsx": str(args.input_xlsx),
        "source_root": str(args.source_root),
        "okei_xsd": "" if okei_xsd is None else str(okei_xsd),
        "okei_unit_count": len(okei_units),
        "object_count": len(object_rows),
        "source_dir_found_count": sum(1 for row in object_rows if row["source_pd_dir"]),
        "tei_found_count": sum(1 for row in object_rows if row["tei_count"]),
        "subgroup_counts": {
            subgroup: sum(1 for row in object_rows if row["project_subgroup"] == subgroup)
            for subgroup in sorted({str(row["project_subgroup"]) for row in object_rows})
        },
        "tei_names": tei_names,
        "tei_canonical_fields": TEI_CANONICAL_FIELDS,
        "outputs": [
            str(args.output_dir / "object_registry_v0.csv"),
            str(args.output_dir / "object_tei_long_v0.csv"),
            str(args.output_dir / "object_registry_v0.jsonl"),
        ],
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
