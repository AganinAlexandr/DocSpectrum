#!/usr/bin/env python3
"""Build experiment C registry groups, similarity gate, and expert arena.

The experiment compares pre-expertise sections reviewed by different experts
inside a fixed organization x work-type x section cell. Expert names are used
only in memory; generated artifacts contain stable hashes and anchor roles.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

from text_features import normalize_text


DEFAULT_REGISTRY = Path(
    r"C:\Users\alexa\OneDrive\Общая\MSE\Объекты MSE_new 2602_24.xlsx"
)
DEFAULT_SECTIONS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0\gip_control_sections_v0.csv"
)
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\expert_quality_experiment_c_v0")

SHEET_NAME = "данные"
HEADER_ROW = 10
DATA_ROW = 11
PLACEHOLDER_DATES = {(2020, 1, 1), (2020, 2, 1)}
SECTION_SCOPE = {"КР", "ПОС"}
COMP_KEYS = (
    "text_count",
    "line_count",
    "frame_count",
    "image_count",
    "table_count",
    "table_cell_count",
    "other_vector_count",
)
WORD_RE = re.compile(r"[0-9a-zа-яё]+", re.IGNORECASE)

# Generic labels keep person names out of generated artifacts.
ANCHOR_BY_NAME = {
    "золотарева": ("ceiling_1_a", "1"),
    "крюкова": ("ceiling_1_b", "1"),
    "левина": ("floor_3", "3"),
    "кузнецов": ("holdout", "holdout"),
}
ACTIVE_CEILING_ROLES = {"ceiling_1_a", "ceiling_1_b"}
REFERENCE_COUNTS = {
    "candidate_group_count": 207,
    "gold_group_count": 97,
    "gate_group_count": 57,
    "arena_holdout_to_floor_pair_count": 149,
    "arena_ceiling_to_floor_pair_count": 53,
    "arena_holdout_to_ceiling_pair_count": 34,
    "arena_holdout_to_ceiling_cell_count": 6,
}

COLUMNS = {
    "object_number": 2,
    "work_type": 7,
    "work_subtype": 8,
    "organization": 9,
    "section": 13,
    "subsection": 14,
    "expert_action": 17,
    "expert_name": 20,
    "session_start": 27,
    "received_remarks": 28,
    "result_1": 29,
    "answer_1": 31,
    "positive_result": 49,
}

XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def normalized_key(value: Any) -> str:
    return normalize_text("" if value is None else str(value))


def expert_hash(value: Any) -> str:
    return stable_hash(normalized_key(value))


def anchor_for_expert(value: Any) -> tuple[str, str]:
    return ANCHOR_BY_NAME.get(normalized_key(value), ("unlabeled", ""))


def excel_date(value: Any) -> datetime | None:
    serial = safe_float(value, -1.0)
    if serial <= 0:
        return None
    return datetime(1899, 12, 30) + timedelta(days=serial)


def date_key(value: Any) -> tuple[int, int, int] | None:
    date_value = excel_date(value)
    if date_value is None:
        return None
    return date_value.year, date_value.month, date_value.day


def date_text(value: Any) -> str:
    date_value = excel_date(value)
    return date_value.strftime("%Y-%m-%d") if date_value else ""


def normalize_object_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\.0$", "", raw)
    digits = "".join(re.findall(r"\d", raw))
    if "_" in raw:
        parts = re.findall(r"\d+", raw)
        if len(parts) >= 2:
            return f"{int(parts[0]):04d}_{int(parts[-1]) % 100:02d}"
    if len(digits) < 3:
        return ""
    year = digits[-2:]
    number = digits[:-2]
    return f"{int(number):04d}_{year}" if number else ""


def classify_section(value: Any) -> str:
    section = str(value or "").strip().upper()
    return section if section in SECTION_SCOPE else ""


def should_drop_registry_row(row: dict[int, Any]) -> str:
    action = normalized_key(row.get(COLUMNS["expert_action"]))
    if "отказ" in action:
        return "expert_refusal"
    if action in {"подп", "подпись"}:
        return "signature_only"
    if date_key(row.get(COLUMNS["received_remarks"])) in PLACEHOLDER_DATES:
        return "placeholder_date"
    return ""


def outcome_flags(row: dict[int, Any]) -> tuple[bool, bool]:
    answer = str(row.get(COLUMNS["answer_1"]) or "").strip()
    result_1 = date_key(row.get(COLUMNS["result_1"]))
    positive = date_key(row.get(COLUMNS["positive_result"]))
    clean_pass = bool(result_1 and positive and result_1 == positive and not answer)
    return clean_pass, bool(answer)


def column_letters(cell_ref: str) -> str:
    match = re.match(r"([A-Z]+)", cell_ref)
    return match.group(1) if match else ""


def column_index(cell_ref: str) -> int:
    letters = column_letters(cell_ref)
    result = 0
    for char in letters:
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(".//x:t", XML_NS))
        for item in root.findall("x:si", XML_NS)
    ]


def resolve_sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_id = ""
    for sheet in workbook.findall("x:sheets/x:sheet", XML_NS):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib.get(f"{{{OFFICE_REL}}}id", "")
            break
    if not rel_id:
        raise KeyError(f"Sheet not found: {sheet_name}")
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relation in relationships.findall("r:Relationship", REL_NS):
        if relation.attrib.get("Id") == rel_id:
            target = relation.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise KeyError(f"Sheet relationship not found: {sheet_name}")


def xlsx_rows(path: Path, sheet_name: str, min_row: int = DATA_ROW) -> list[dict[int, Any]]:
    # Copy first so Excel/OneDrive locking cannot change the stream mid-read.
    with tempfile.TemporaryDirectory(prefix="docspectrum_experiment_c_") as temp_dir:
        copy_path = Path(temp_dir) / path.name
        shutil.copy2(path, copy_path)
        with zipfile.ZipFile(copy_path) as archive:
            shared = read_shared_strings(archive)
            sheet_path = resolve_sheet_path(archive, sheet_name)
            root = ET.fromstring(archive.read(sheet_path))

    rows: list[dict[int, Any]] = []
    for row_node in root.findall("x:sheetData/x:row", XML_NS):
        row_number = int(row_node.attrib.get("r", "0"))
        if row_number < min_row:
            continue
        values: dict[int, Any] = {}
        for cell in row_node.findall("x:c", XML_NS):
            index = column_index(cell.attrib.get("r", ""))
            cell_type = cell.attrib.get("t", "")
            if cell_type == "inlineStr":
                value: Any = "".join(
                    node.text or "" for node in cell.findall(".//x:t", XML_NS)
                )
            else:
                node = cell.find("x:v", XML_NS)
                value = node.text if node is not None and node.text is not None else ""
                if cell_type == "s" and value != "":
                    value = shared[int(value)]
            values[index] = value
        rows.append(values)
    return rows


def build_registry_rows(raw_rows: list[dict[int, Any]]) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    drops: Counter[str] = Counter()
    for raw in raw_rows:
        object_id = normalize_object_id(raw.get(COLUMNS["object_number"]))
        if not object_id:
            if str(raw.get(COLUMNS["object_number"]) or "").strip():
                drops["invalid_object_id"] += 1
            continue
        drop_reason = should_drop_registry_row(raw)
        if drop_reason:
            drops[drop_reason] += 1
            continue
        section = classify_section(raw.get(COLUMNS["section"]))
        clean_pass, has_remark = outcome_flags(raw)
        expert_name = str(raw.get(COLUMNS["expert_name"]) or "").strip()
        anchor_role, quality_class = anchor_for_expert(expert_name)
        rows.append(
            {
                "object_id": object_id,
                "organization": str(raw.get(COLUMNS["organization"]) or "").strip(),
                "work_type": str(raw.get(COLUMNS["work_type"]) or "").strip(),
                "work_subtype": str(raw.get(COLUMNS["work_subtype"]) or "").strip(),
                "section_code": section,
                "expert_hash": expert_hash(expert_name) if expert_name else "",
                "expert_anchor_role": anchor_role,
                "expert_quality_class": quality_class,
                "session_start_date": date_text(raw.get(COLUMNS["session_start"])),
                "has_first_round_remark": has_remark,
                "clean_first_round_pass": clean_pass,
            }
        )
    return rows, drops


def group_id(key: tuple[str, str, str]) -> str:
    return stable_hash("\x1f".join(key))


def build_groups(registry_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in registry_rows:
        if row["section_code"] not in SECTION_SCOPE:
            continue
        key = (row["organization"], row["work_type"], row["section_code"])
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    candidates: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for key, members in sorted(grouped.items()):
        objects = {row["object_id"] for row in members}
        experts = {row["expert_hash"] for row in members if row["expert_hash"]}
        if len(objects) < 2 or len(experts) < 2:
            continue
        candidates[key] = members
        labeled_with_remarks = {
            row["expert_anchor_role"]
            for row in members
            if row["expert_anchor_role"] != "unlabeled" and row["has_first_round_remark"]
        }
        labeled = {
            row["expert_anchor_role"]
            for row in members
            if row["expert_anchor_role"] != "unlabeled"
        }
        output.append(
            {
                "group_id": group_id(key),
                "organization": key[0],
                "work_type": key[1],
                "section_code": key[2],
                "object_count": len(objects),
                "expert_count": len(experts),
                "anchor_role_count": len(labeled),
                "anchor_roles_with_remarks_count": len(labeled_with_remarks),
                "remark_row_count": sum(bool(row["has_first_round_remark"]) for row in members),
                "clean_pass_row_count": sum(bool(row["clean_first_round_pass"]) for row in members),
                "candidate_status": "candidate",
                "gold_status": "gold" if len(labeled_with_remarks) >= 2 else "not_gold",
            }
        )
    return output, candidates


def load_section_index(path: Path, export_root: Path) -> dict[tuple[str, str], str]:
    selected: dict[tuple[str, str], tuple[int, str]] = {}
    for row in read_csv(path):
        section = row.get("section_code", "").strip().upper()
        if section not in SECTION_SCOPE:
            continue
        bundle = row.get("bundle_id", "").strip()
        if not bundle or not (export_root / bundle).is_dir():
            continue
        key = (row.get("object_id", "").strip(), section)
        size = int(safe_float(row.get("file_size_bytes"), 0))
        if key not in selected or size >= selected[key][0]:
            selected[key] = (size, bundle)
    return {key: value[1] for key, value in selected.items()}


def read_bundle_profile(bundle_dir: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    page_count = 0
    page_summary = bundle_dir / "page_summary.csv"
    if page_summary.exists():
        for row in read_csv(page_summary):
            page_count += 1
            for key in COMP_KEYS:
                counts[key] += safe_float(row.get(key))
    total = sum(counts.values()) or 1.0
    composition = {key: counts[key] / total for key in COMP_KEYS}

    tokens: list[str] = []
    text_segments = bundle_dir / "text_segments.csv"
    if text_segments.exists():
        for row in read_csv(text_segments):
            value = normalize_text(row.get("normalized_text", ""))
            if value:
                tokens.extend(WORD_RE.findall(value))
    shingles = {
        " ".join(tokens[index : index + 5])
        for index in range(max(0, len(tokens) - 4))
    }
    return {
        "composition": composition,
        "shingles": shingles,
        "page_count": page_count,
        "token_count": len(tokens),
        "element_count": int(sum(counts.values())),
    }


def composition_cosine(left: dict[str, float], right: dict[str, float]) -> float:
    numerator = sum(left.get(key, 0.0) * right.get(key, 0.0) for key in COMP_KEYS)
    left_norm = math.sqrt(sum(left.get(key, 0.0) ** 2 for key in COMP_KEYS))
    right_norm = math.sqrt(sum(right.get(key, 0.0) ** 2 for key in COMP_KEYS))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def set_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def pair_arena_class(left_roles: set[str], right_roles: set[str]) -> str:
    left_holdout = "holdout" in left_roles
    right_holdout = "holdout" in right_roles
    left_ceiling = bool(left_roles & ACTIVE_CEILING_ROLES)
    right_ceiling = bool(right_roles & ACTIVE_CEILING_ROLES)
    left_floor = "floor_3" in left_roles
    right_floor = "floor_3" in right_roles
    # The holdout must occur on exactly one side. If both objects were reviewed
    # by the holdout, the pair does not isolate a cross-expert contrast.
    if left_holdout != right_holdout:
        if (left_holdout and right_ceiling) or (right_holdout and left_ceiling):
            return "holdout_to_ceiling"
        if (left_holdout and right_floor) or (right_holdout and left_floor):
            return "holdout_to_floor"
    if (left_ceiling and right_floor) or (right_ceiling and left_floor):
        return "ceiling_to_floor"
    if left_ceiling and right_ceiling:
        return "ceiling_to_ceiling"
    return "other"


def build_gate_and_arena(
    candidates: dict[tuple[str, str, str], list[dict[str, Any]]],
    section_index: dict[tuple[str, str], str],
    export_root: Path,
    shingle_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    profile_cache: dict[str, dict[str, Any]] = {}
    gate_rows: list[dict[str, Any]] = []
    arena_rows: list[dict[str, Any]] = []

    for key, members in sorted(candidates.items()):
        labeled_with_remarks = {
            row["expert_anchor_role"]
            for row in members
            if row["expert_anchor_role"] != "unlabeled" and row["has_first_round_remark"]
        }
        if len(labeled_with_remarks) < 2:
            continue

        expert_roles_by_object: dict[str, set[str]] = defaultdict(set)
        expert_hashes_by_object: dict[str, set[str]] = defaultdict(set)
        for row in members:
            expert_hashes_by_object[row["object_id"]].add(row["expert_hash"])
            expert_roles_by_object[row["object_id"]].add(row["expert_anchor_role"])

        profiles: dict[str, dict[str, Any]] = {}
        bundle_by_object: dict[str, str] = {}
        for object_id in sorted(expert_hashes_by_object):
            bundle = section_index.get((object_id, key[2]))
            if not bundle:
                continue
            if bundle not in profile_cache:
                profile_cache[bundle] = read_bundle_profile(export_root / bundle)
            profiles[object_id] = profile_cache[bundle]
            bundle_by_object[object_id] = bundle
        objects = sorted(profiles)
        if len(objects) < 2:
            continue

        shingle_values: list[float] = []
        composition_values: list[float] = []
        cross_expert_pair_count = 0
        cross_expert_near_pair_count = 0
        for left_index, left_object in enumerate(objects):
            for right_object in objects[left_index + 1 :]:
                left_profile = profiles[left_object]
                right_profile = profiles[right_object]
                shingle = set_jaccard(left_profile["shingles"], right_profile["shingles"])
                composition = composition_cosine(
                    left_profile["composition"], right_profile["composition"]
                )
                shingle_values.append(shingle)
                composition_values.append(composition)
                if expert_hashes_by_object[left_object] == expert_hashes_by_object[right_object]:
                    continue
                cross_expert_pair_count += 1
                if shingle < shingle_threshold:
                    continue
                cross_expert_near_pair_count += 1
                arena_class = pair_arena_class(
                    expert_roles_by_object[left_object],
                    expert_roles_by_object[right_object],
                )
                arena_rows.append(
                    {
                        "group_id": group_id(key),
                        "organization": key[0],
                        "work_type": key[1],
                        "section_code": key[2],
                        "left_object_id": left_object,
                        "right_object_id": right_object,
                        "left_bundle_id": bundle_by_object[left_object],
                        "right_bundle_id": bundle_by_object[right_object],
                        "left_expert_hashes": "|".join(sorted(expert_hashes_by_object[left_object])),
                        "right_expert_hashes": "|".join(sorted(expert_hashes_by_object[right_object])),
                        "left_anchor_roles": "|".join(sorted(expert_roles_by_object[left_object])),
                        "right_anchor_roles": "|".join(sorted(expert_roles_by_object[right_object])),
                        "arena_class": arena_class,
                        "text_shingle_jaccard": round_float(shingle),
                        "composition_cosine": round_float(composition),
                        "left_page_count": left_profile["page_count"],
                        "right_page_count": right_profile["page_count"],
                        "left_element_count": left_profile["element_count"],
                        "right_element_count": right_profile["element_count"],
                    }
                )

        gate_rows.append(
            {
                "group_id": group_id(key),
                "organization": key[0],
                "work_type": key[1],
                "section_code": key[2],
                "exported_object_count": len(objects),
                "pair_count": len(shingle_values),
                "cross_expert_pair_count": cross_expert_pair_count,
                "cross_expert_near_pair_count": cross_expert_near_pair_count,
                "median_text_shingle_jaccard": round_float(median(shingle_values)),
                "max_text_shingle_jaccard": round_float(max(shingle_values)),
                "median_composition_cosine": round_float(median(composition_values)),
                "gate_status": (
                    "passed_pair_level_near_identity"
                    if cross_expert_near_pair_count
                    else "measured_no_near_identity_pair"
                ),
            }
        )

    cell_counts: Counter[tuple[str, str]] = Counter()
    for row in arena_rows:
        cell_counts[(row["group_id"], row["arena_class"])] += 1
    cell_rows = []
    gate_by_id = {row["group_id"]: row for row in gate_rows}
    for (current_group_id, arena_class), pair_count in sorted(cell_counts.items()):
        gate = gate_by_id[current_group_id]
        cell_rows.append(
            {
                "group_id": current_group_id,
                "organization": gate["organization"],
                "work_type": gate["work_type"],
                "section_code": gate["section_code"],
                "arena_class": arena_class,
                "pair_count": pair_count,
            }
        )
    return gate_rows, arena_rows, cell_rows


def count_arena(arena_rows: list[dict[str, Any]], cell_rows: list[dict[str, Any]]) -> dict[str, int]:
    pairs = Counter(row["arena_class"] for row in arena_rows)
    return {
        "arena_holdout_to_floor_pair_count": pairs["holdout_to_floor"],
        "arena_ceiling_to_floor_pair_count": pairs["ceiling_to_floor"],
        "arena_holdout_to_ceiling_pair_count": pairs["holdout_to_ceiling"],
        "arena_holdout_to_ceiling_cell_count": sum(
            row["arena_class"] == "holdout_to_ceiling" for row in cell_rows
        ),
    }


def build(
    registry_path: Path,
    sections_path: Path,
    export_root: Path,
    output_dir: Path,
    shingle_threshold: float,
    assert_reference: bool = False,
) -> dict[str, Any]:
    raw_rows = xlsx_rows(registry_path, SHEET_NAME)
    registry_rows, drops = build_registry_rows(raw_rows)
    group_rows, candidates = build_groups(registry_rows)
    section_index = load_section_index(sections_path, export_root)
    gate_rows, arena_rows, cell_rows = build_gate_and_arena(
        candidates,
        section_index,
        export_root,
        shingle_threshold,
    )

    counts = {
        "source_data_row_count": len(raw_rows),
        "kept_registry_row_count": len(registry_rows),
        "candidate_group_count": len(group_rows),
        "gold_group_count": sum(row["gold_status"] == "gold" for row in group_rows),
        "gate_group_count": len(gate_rows),
        **count_arena(arena_rows, cell_rows),
    }
    reference_check = {
        key: {
            "expected": expected,
            "actual": counts[key],
            "status": "matched" if counts[key] == expected else "changed",
        }
        for key, expected in REFERENCE_COUNTS.items()
    }
    if assert_reference:
        changed = {key: value for key, value in reference_check.items() if value["status"] != "matched"}
        if changed:
            raise ValueError(f"Experiment C reference counts changed: {changed}")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "expert_quality_registry_rows_v0.csv",
        registry_rows,
        [
            "object_id",
            "organization",
            "work_type",
            "work_subtype",
            "section_code",
            "expert_hash",
            "expert_anchor_role",
            "expert_quality_class",
            "session_start_date",
            "has_first_round_remark",
            "clean_first_round_pass",
        ],
    )
    write_csv(
        output_dir / "expert_quality_groups_v0.csv",
        group_rows,
        [
            "group_id",
            "organization",
            "work_type",
            "section_code",
            "object_count",
            "expert_count",
            "anchor_role_count",
            "anchor_roles_with_remarks_count",
            "remark_row_count",
            "clean_pass_row_count",
            "candidate_status",
            "gold_status",
        ],
    )
    write_csv(
        output_dir / "expert_quality_gate_groups_v0.csv",
        gate_rows,
        [
            "group_id",
            "organization",
            "work_type",
            "section_code",
            "exported_object_count",
            "pair_count",
            "cross_expert_pair_count",
            "cross_expert_near_pair_count",
            "median_text_shingle_jaccard",
            "max_text_shingle_jaccard",
            "median_composition_cosine",
            "gate_status",
        ],
    )
    write_csv(
        output_dir / "expert_quality_arena_pairs_v0.csv",
        arena_rows,
        [
            "group_id",
            "organization",
            "work_type",
            "section_code",
            "left_object_id",
            "right_object_id",
            "left_bundle_id",
            "right_bundle_id",
            "left_expert_hashes",
            "right_expert_hashes",
            "left_anchor_roles",
            "right_anchor_roles",
            "arena_class",
            "text_shingle_jaccard",
            "composition_cosine",
            "left_page_count",
            "right_page_count",
            "left_element_count",
            "right_element_count",
        ],
    )
    write_csv(
        output_dir / "expert_quality_arena_cells_v0.csv",
        cell_rows,
        [
            "group_id",
            "organization",
            "work_type",
            "section_code",
            "arena_class",
            "pair_count",
        ],
    )
    summary = {
        "schema_version": "expert_quality_experiment_c_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "registry_path": str(registry_path),
            "sections_path": str(sections_path),
            "export_root": str(export_root),
        },
        "parameters": {
            "section_scope": sorted(SECTION_SCOPE),
            "shingle_size": 5,
            "arena_shingle_threshold": shingle_threshold,
            "group_key": ["organization", "work_type", "section_code"],
            "expert_identity_output": "sha1_only",
        },
        "counts": counts,
        "drop_reasons": dict(sorted(drops.items())),
        "reference_check": reference_check,
        "interpretation": {
            "gate": "near_identity_admission_test_on_pre_expertise_sections",
            "arena": "cross_expert_pairs_only; not_an_expert_quality_verdict",
            "class_1": "ceiling_anchor",
            "holdout": "conditional_expert; evaluate_session_variance_not_only_mean",
            "blocked": "remark_content_recall_and_post_expertise_delta",
        },
    }
    write_json(output_dir / "expert_quality_experiment_c_v0.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build DocSpectrum experiment C registry, gate, and arena artifacts."
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--shingle-threshold", type=float, default=0.70)
    parser.add_argument("--assert-reference", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build(
        args.registry,
        args.sections,
        args.export_root,
        args.output_dir,
        args.shingle_threshold,
        args.assert_reference,
    )
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
