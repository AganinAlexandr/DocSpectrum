#!/usr/bin/env python3
"""Build a reviewable alias registry for organizations from title extraction."""

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

from text_features import normalize_text


DEFAULT_RESULTS_ROOT = Path(r"E:\output\DocSpectrum")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\org_alias_registry_v0")
DEFAULT_REGISTRY_XLSX = Path(r"E:\commons\DocSpectrum\Капремонт_Объекты.xlsx")

LEGAL_FORM_PATTERNS = (
    ("ООО", r"\b(?:ооо|000)\b"),
    ("АО", r"\bао\b"),
    ("ПАО", r"\bпао\b"),
    ("ОАО", r"\bоао\b"),
    ("ЗАО", r"\bзао\b"),
    ("ИП", r"\bип\b"),
)

SPELLING_TRANSLATION = str.maketrans(
    {
        "ɋ": "С",
        "ɬ": "т",
        "ɪ": "р",
        "ɨ": "о",
        "ɣ": "й",
        "Ɇ": "М",
        "ɧ": "н",
        "ɚ": "а",
        "ɠ": "ж",
        "ɉ": "П",
        "ʜ": "Н",
        "ᴏ": "О",
        "ᴍ": "М",
        "ᴛ": "Т",
        "ᴀ": "А",
        "ᴩ": "Р",
        "ᴄ": "С",
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def party_files(results_root: Path) -> list[Path]:
    return sorted(
        results_root.glob("title_authorship_range_*_results_v0/title_authorship_parties_v0.csv")
    )


def column_letters(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref)
    return match.group(1) if match else ""


def read_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for item in root.findall("a:si", namespace):
        text = "".join(node.text or "" for node in item.findall(".//a:t", namespace))
        values.append(text)
    return values


def resolve_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    main_ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rel_ns = {"a": "http://schemas.openxmlformats.org/package/2006/relationships"}
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    target_id = ""
    for sheet in workbook.findall("a:sheets/a:sheet", main_ns):
        if sheet.attrib.get("name") == sheet_name:
            target_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
            break
    if not target_id:
        raise KeyError(f"Sheet not found: {sheet_name}")
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("a:Relationship", rel_ns):
        if rel.attrib.get("Id") == target_id:
            return "xl/" + rel.attrib["Target"].lstrip("/")
    raise KeyError(f"Sheet relationship not found: {sheet_name}")


def sheet_rows_from_xlsx(path: Path, sheet_name: str) -> list[dict[str, str]]:
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared_strings = read_xlsx_shared_strings(zf)
        sheet_path = resolve_sheet_path(zf, sheet_name)
        root = ET.fromstring(zf.read(sheet_path))
    rows = []
    for row in root.findall("a:sheetData/a:row", namespace):
        values: dict[str, str] = {}
        for cell in row.findall("a:c", namespace):
            ref = cell.attrib.get("r", "")
            column = column_letters(ref)
            value = ""
            cell_type = cell.attrib.get("t", "")
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//a:t", namespace))
            else:
                node = cell.find("a:v", namespace)
                if node is not None and node.text is not None:
                    value = node.text
                    if cell_type == "s":
                        value = shared_strings[int(value)]
            values[column] = value
        rows.append(values)
    return rows


def capremont_registry_by_object_id(path: Path) -> dict[str, dict[str, str]]:
    rows = sheet_rows_from_xlsx(path, "объекты")
    header_row = next(
        row
        for row in rows
        if "номер" in row.values() and "проектировщик" in row.values()
    )
    reverse_header = {value: key for key, value in header_row.items() if value}
    number_col = reverse_header["номер"]
    designer_col = reverse_header["проектировщик"]
    contractor_col = reverse_header["генПодрядчик"]
    result = {}
    header_seen = False
    for row in rows:
        if row is header_row:
            header_seen = True
            continue
        if not header_seen:
            continue
        number = row.get(number_col, "").strip()
        if not number:
            continue
        result[number] = {
            "проектировщик": row.get(designer_col, "").strip(),
            "генПодрядчик": row.get(contractor_col, "").strip(),
        }
    return result


def normalize_org_text(value: str) -> str:
    return normalize_text(value.translate(SPELLING_TRANSLATION))


def extract_quoted_name(text: str) -> str:
    text = text.translate(SPELLING_TRANSLATION)
    patterns = (
        r"«\s*([^»]{2,}?)\s*»",
        r'"([^"]{2,}?)"',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_org_text(match.group(1))
    return ""


def detect_legal_form(text: str) -> str:
    normalized = normalize_org_text(text)
    for label, pattern in LEGAL_FORM_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return label
    if "общество с ограниченной ответственностью" in normalized:
        return "ООО"
    if "акционерное общество" in normalized:
        return "АО"
    return ""


def identity_hint(raw: str, evidence: str) -> tuple[str, str, str]:
    best_source = evidence or raw
    quoted = extract_quoted_name(raw) or extract_quoted_name(best_source)
    legal_form = detect_legal_form(raw) or detect_legal_form(best_source)
    normalized_raw = normalize_org_text(raw or best_source)
    if quoted:
        key = quoted
        display = f"{legal_form} «{quoted}»".strip() if legal_form else f"«{quoted}»"
    else:
        key = re.sub(
            r"\b(?:ооо|000|ао|пао|оао|зао|ип|общество|с|ограниченной|ответственностью)\b",
            " ",
            normalized_raw,
        )
        key = " ".join(key.split()) or normalized_raw
        display = normalized_raw
    return key, display, legal_form


def object_registry_key(object_id: str) -> str:
    return object_id.replace("_", "")


def match_registry_name(
    hint_key: str,
    role: str,
    registry_projectirovshik: str,
    registry_genpodryadchik: str,
) -> str:
    if role == "subcontractor":
        candidates = [candidate for candidate in (registry_projectirovshik,) if candidate]
    elif registry_genpodryadchik:
        candidates = [registry_genpodryadchik]
    else:
        candidates = [candidate for candidate in (registry_projectirovshik,) if candidate]
    if not candidates:
        return ""
    compact_hint = hint_key.replace(" ", "")
    for candidate in candidates:
        candidate_hint, _display, _legal = identity_hint(candidate, candidate)
        compact_candidate = candidate_hint.replace(" ", "")
        if (
            candidate_hint == hint_key
            or candidate_hint in hint_key
            or hint_key in candidate_hint
            or compact_candidate == compact_hint
            or compact_candidate in compact_hint
            or compact_hint in compact_candidate
        ):
            return candidate
    return ""


def build(results_root: Path, output_dir: Path, registry_xlsx: Path) -> dict[str, Any]:
    files = party_files(results_root)
    object_registry = (
        capremont_registry_by_object_id(registry_xlsx)
        if registry_xlsx.is_file()
        else {}
    )
    rows = []
    for path in files:
        corpus_id = path.parent.name.replace("title_authorship_range_", "").replace("_results_v0", "")
        for row in read_csv(path):
            if not (row.get("organization_name_raw") or row.get("organization_evidence_text")):
                continue
            hint_key, display, legal_form = identity_hint(
                row.get("organization_name_raw", ""),
                row.get("organization_evidence_text", ""),
            )
            registry_entry = object_registry.get(object_registry_key(row["object_id"]), {})
            registry_projectirovshik = registry_entry.get("проектировщик", "")
            registry_genpodryadchik = registry_entry.get("генПодрядчик", "")
            registry_match = match_registry_name(
                hint_key,
                row["role"],
                registry_projectirovshik,
                registry_genpodryadchik,
            )
            rows.append(
                {
                    "corpus_id": corpus_id,
                    "object_id": row["object_id"],
                    "role": row["role"],
                    "section_code": row["section_code"],
                    "organization_name_raw": row.get("organization_name_raw", ""),
                    "organization_evidence_text": row.get("organization_evidence_text", ""),
                    "organization_name_normalized": row.get("organization_name_normalized", ""),
                    "organization_identity_hint": hint_key,
                    "organization_display_hint": display,
                    "organization_legal_form_hint": legal_form,
                    "registry_projectirovshik": registry_projectirovshik,
                    "registry_genpodryadchik": registry_genpodryadchik,
                    "registry_canonical_match": registry_match,
                }
            )

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["organization_identity_hint"]].append(row)

    registry_rows: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []
    for group_index, (hint, group_rows) in enumerate(sorted(groups.items()), start=1):
        raw_counter = Counter(row["organization_name_raw"] for row in group_rows if row["organization_name_raw"])
        display_counter = Counter(row["organization_display_hint"] for row in group_rows if row["organization_display_hint"])
        legal_form_counter = Counter(row["organization_legal_form_hint"] for row in group_rows if row["organization_legal_form_hint"])
        registry_counter = Counter(
            row["registry_canonical_match"]
            for row in group_rows
            if row["registry_canonical_match"]
        )
        canonical_display = (
            registry_counter.most_common(1)[0][0]
            if registry_counter
            else display_counter.most_common(1)[0][0]
            if display_counter
            else hint
        )
        alias_id = f"org_alias_v0_{group_index:03d}"
        registry_rows.append(
            {
                "alias_id": alias_id,
                "organization_identity_hint": hint,
                "canonical_display_hint": canonical_display,
                "canonical_legal_form_hint": legal_form_counter.most_common(1)[0][0] if legal_form_counter else "",
                "canonical_source": "capremont_registry" if registry_counter else "title_ocr",
                "party_count": len(group_rows),
                "object_count": len({row["object_id"] for row in group_rows}),
                "role_count": len({row["role"] for row in group_rows}),
                "variant_count": len(raw_counter),
                "registry_match_count": sum(registry_counter.values()),
                "needs_alias_review": len(raw_counter) > 1 or canonical_display != hint,
                "example_objects": ";".join(sorted({row["object_id"] for row in group_rows})[:10]),
            }
        )
        for raw_value, count in raw_counter.items():
            sample = next(row for row in group_rows if row["organization_name_raw"] == raw_value)
            variant_rows.append(
                {
                    "alias_id": alias_id,
                    "organization_identity_hint": hint,
                    "canonical_display_hint": canonical_display,
                    "organization_name_raw": raw_value,
                    "organization_name_normalized": sample["organization_name_normalized"],
                    "organization_evidence_text": sample["organization_evidence_text"],
                    "organization_legal_form_hint": sample["organization_legal_form_hint"],
                    "registry_projectirovshik": sample["registry_projectirovshik"],
                    "registry_genpodryadchik": sample["registry_genpodryadchik"],
                    "registry_canonical_match": sample["registry_canonical_match"],
                    "party_count": count,
                    "object_count": len(
                        {
                            row["object_id"]
                            for row in group_rows
                            if row["organization_name_raw"] == raw_value
                        }
                    ),
                    "sample_object_id": sample["object_id"],
                    "sample_section_code": sample["section_code"],
                    "sample_role": sample["role"],
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    if registry_rows:
        write_csv(output_dir / "org_alias_registry_v0.csv", registry_rows)
        write_csv(output_dir / "org_alias_variants_v0.csv", variant_rows)

    summary = {
        "schema_version": "org_alias_registry_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_file_count": len(files),
        "party_row_count": len(rows),
        "identity_group_count": len(registry_rows),
        "variant_row_count": len(variant_rows),
        "review_group_count": sum(bool(row["needs_alias_review"]) for row in registry_rows),
        "capremont_registry_path": str(registry_xlsx) if registry_xlsx.is_file() else "",
        "files": {
            "registry": "org_alias_registry_v0.csv",
            "variants": "org_alias_variants_v0.csv",
        },
    }
    (output_dir / "org_alias_registry_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build organization alias registry from title-party outputs."
    )
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--registry-xlsx", type=Path, default=DEFAULT_REGISTRY_XLSX)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.results_root, args.output_dir, args.registry_xlsx),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
