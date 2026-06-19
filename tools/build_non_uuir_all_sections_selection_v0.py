#!/usr/bin/env python3
"""Build an all-sections non-UUiR explorer selection from the wide corpus."""

from __future__ import annotations

import argparse
import csv
import json
import re
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = Path(r"E:\output\DocSpectrum\gip_corpus_candidates_v0.csv")
DEFAULT_SOURCE_ROOT = Path(r"E:\MSE_арх")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\non_uuir_all_sections_selection_v0")
UUIR_GROUP = "УУиР"
OBJECT_RE = re.compile(r"^(?P<number>\d{4})_25(?:\D|$)")
REQUIRED_EXPORT_FILES = {
    "manifest.json",
    "documents.csv",
    "pages.csv",
    "elements.csv",
    "text_segments.csv",
    "tables.csv",
    "table_cells.csv",
}

EXCLUDE_PATTERNS = (
    "иул",
    "уил",
    "выпис",
    "договор",
    "допсоглаш",
    "заявлен",
    "доверен",
    "ноприз",
    "сро",
    "членств",
    "свидетельств",
)

EXCLUDE_NAME_PREFIXES = (
    "тз_",
    "ао_",
    "дв_",
)

EXCLUDE_NAME_SNIPPETS = (
    " техническое задание",
    "техническое задание ",
    " акт обслед",
    "дефектная ведомост",
)

SECTION_MARKERS = (
    ("ПОС", ("ПОС", "ПОКР")),
    ("ПЗ", ("ПЗ", "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА")),
    ("АР", ("АР",)),
    ("КР", ("КР",)),
    ("ОВ", ("ОВ",)),
    ("ВК", ("ВК",)),
    ("ЭС", ("ЭС",)),
    ("СС", ("СС",)),
    ("СМ", ("СМ",)),
    ("ФАСАД", ("ФАСАД",)),
    ("ФУНДАМЕНТ", ("ФУНДАМЕНТ",)),
    ("БАЛКОНЫ", ("БАЛКОН", "БАЛКОНЫ")),
    ("ЧЕРДАК", ("ЧЕРДАК",)),
    ("КРОВЛЯ", ("КРОВЛ",)),
    ("ТЕПЛОВИЗОР", ("ТЕПЛОВИЗ",)),
    ("ИНЖЕНЕРИЯ", ("ИОС",)),
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def object_id_from_number(source_number: str) -> str:
    return f"{source_number[:4]}_25"


def object_directories(source_root: Path, start: int, end: int) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in source_root.iterdir():
        if not path.is_dir():
            continue
        match = OBJECT_RE.match(path.name)
        if not match:
            continue
        number = int(match.group("number"))
        if start <= number <= end:
            result[f"{number}_25"] = path
    return result


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def should_exclude_pdf(path: Path) -> tuple[bool, str]:
    haystack = normalize_name(str(path))
    for marker in EXCLUDE_PATTERNS:
        if marker in haystack:
            return True, marker
    file_name = normalize_name(path.name)
    trimmed_name = re.sub(r"^\d+(?:\.\d+)*\s*", "", file_name)
    for prefix in EXCLUDE_NAME_PREFIXES:
        if trimmed_name.startswith(prefix):
            return True, prefix.rstrip("_")
    for snippet in EXCLUDE_NAME_SNIPPETS:
        if snippet in f" {file_name}":
            return True, snippet.strip()
    return False, ""


def infer_section_code(file_name: str) -> str:
    upper_name = file_name.upper()
    for code, markers in SECTION_MARKERS:
        if any(marker.upper() in upper_name for marker in markers):
            return code
    return "UNKNOWN"


def crc32_file(path: Path) -> str:
    value = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value = zlib.crc32(chunk, value)
    return f"{value & 0xFFFFFFFF:08x}"


def is_complete_export(export_root: Path, document_id: str) -> bool:
    path = export_root / document_id
    return path.is_dir() and REQUIRED_EXPORT_FILES.issubset(
        {item.name for item in path.iterdir() if item.is_file()}
    )


def build(
    candidates_path: Path,
    source_root: Path,
    export_root: Path,
    output_dir: Path,
    start: int,
    end: int,
) -> dict[str, Any]:
    generated_at = now()
    num_col = "номер"
    address_col = "название"
    gip_col = "dev_ГИП(доп_2)"
    designer_col = "орг(проектировщик)"
    work_group_col = "группа(вид_работ)"
    work_subgroup_col = "подГруппа"
    year_col = "год"

    registry_rows = read_csv(candidates_path, delimiter=";")
    object_dirs = object_directories(source_root, start, end)

    candidate_rows = []
    for row in registry_rows:
        source_number = row.get(num_col, "")
        if not source_number or len(source_number) < 4:
            continue
        object_id = object_id_from_number(source_number)
        match = OBJECT_RE.match(object_id)
        if not match:
            continue
        number = int(match.group("number"))
        if not (start <= number <= end):
            continue
        if row.get(work_group_col, "").strip() == UUIR_GROUP:
            continue
        candidate_rows.append(
            {
                "object_id": object_id,
                "source_number": source_number,
                "address": row.get(address_col, ""),
                "registry_gip": row.get(gip_col, ""),
                "registry_org": row.get(designer_col, ""),
                "work_group": row.get(work_group_col, ""),
                "work_subgroup": row.get(work_subgroup_col, ""),
                "year": row.get(year_col, ""),
                "source_dir": str(object_dirs.get(object_id, "")),
            }
        )

    source_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    by_crc: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for candidate in sorted(candidate_rows, key=lambda row: row["object_id"]):
        source_dir = Path(candidate["source_dir"]) if candidate["source_dir"] else None
        if source_dir is None or not source_dir.exists():
            excluded_rows.append(
                {
                    **candidate,
                    "source_pdf_path": "",
                    "source_pdf_name": "",
                    "exclude_reason": "source_dir_missing",
                }
            )
            continue
        for pdf_path in sorted(source_dir.rglob("*.pdf")):
            excluded, reason = should_exclude_pdf(pdf_path)
            if excluded:
                excluded_rows.append(
                    {
                        **candidate,
                        "source_pdf_path": str(pdf_path),
                        "source_pdf_name": pdf_path.name,
                        "exclude_reason": reason,
                    }
                )
                continue
            crc32 = crc32_file(pdf_path)
            document_id = f"doc_{crc32}"
            row = {
                **candidate,
                "section_code": infer_section_code(pdf_path.name),
                "source_pdf_path": str(pdf_path),
                "source_pdf_name": pdf_path.name,
                "file_size_bytes": pdf_path.stat().st_size,
                "file_mtime_utc": datetime.fromtimestamp(pdf_path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
                "crc32": crc32,
                "expected_document_id": document_id,
                "export_exists_at_build": is_complete_export(export_root, document_id),
                "selection_rule": "all_sections_non_uuir",
            }
            source_rows.append(row)
            by_crc[crc32].append(row)

    unique_rows: list[dict[str, Any]] = []
    for crc32, rows in sorted(by_crc.items()):
        primary = sorted(
            rows,
            key=lambda row: (
                row["object_id"],
                row["section_code"],
                row["source_pdf_name"],
            ),
        )[0]
        unique_rows.append(
            {
                "object_id": primary["object_id"],
                "source_number": primary["source_number"],
                "address": primary["address"],
                "section_code": primary["section_code"],
                "analysis_target_pdf": primary["source_pdf_path"],
                "source_file_name": primary["source_pdf_name"],
                "file_size_bytes": primary["file_size_bytes"],
                "crc32": crc32,
                "expected_document_id": primary["expected_document_id"],
                "staging_file_name": primary["source_pdf_name"],
                "staging_path": primary["source_pdf_path"],
                "version_count": 1,
                "title_extraction_status": "not_applicable_all_sections_run",
                "linked_object_ids": "|".join(sorted({row["object_id"] for row in rows})),
                "linked_section_codes": "|".join(sorted({row["section_code"] for row in rows})),
                "duplicate_source_count": len(rows),
                "export_exists_at_build": primary["export_exists_at_build"],
                "selection_rule": "all_sections_non_uuir|crc_dedup",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    source_fields = [
        "object_id",
        "source_number",
        "address",
        "registry_gip",
        "registry_org",
        "work_group",
        "work_subgroup",
        "year",
        "source_dir",
        "section_code",
        "source_pdf_path",
        "source_pdf_name",
        "file_size_bytes",
        "file_mtime_utc",
        "crc32",
        "expected_document_id",
        "export_exists_at_build",
        "selection_rule",
    ]
    excluded_fields = [
        "object_id",
        "source_number",
        "address",
        "registry_gip",
        "registry_org",
        "work_group",
        "work_subgroup",
        "year",
        "source_dir",
        "source_pdf_path",
        "source_pdf_name",
        "exclude_reason",
    ]
    unique_fields = [
        "object_id",
        "source_number",
        "address",
        "section_code",
        "analysis_target_pdf",
        "source_file_name",
        "file_size_bytes",
        "crc32",
        "expected_document_id",
        "staging_file_name",
        "staging_path",
        "version_count",
        "title_extraction_status",
        "linked_object_ids",
        "linked_section_codes",
        "duplicate_source_count",
        "export_exists_at_build",
        "selection_rule",
    ]
    write_csv(output_dir / "all_sections_source_inventory_v0.csv", source_rows, source_fields)
    write_csv(output_dir / "all_sections_excluded_v0.csv", excluded_rows, excluded_fields)
    write_csv(output_dir / "all_sections_run_selection_v0.csv", unique_rows, unique_fields)

    summary = {
        "schema_version": "non_uuir_all_sections_selection_v0",
        "generated_at": generated_at,
        "range": f"{start}_25..{end}_25",
        "candidate_object_count": len(candidate_rows),
        "included_object_count": len({row["object_id"] for row in source_rows}),
        "source_pdf_count": len(source_rows),
        "unique_crc32_count": len(unique_rows),
        "excluded_row_count": len(excluded_rows),
        "existing_export_count_at_build": sum(bool(row["export_exists_at_build"]) for row in unique_rows),
        "missing_export_count_at_build": sum(not bool(row["export_exists_at_build"]) for row in unique_rows),
        "section_counts": dict(sorted(Counter(row["section_code"] for row in source_rows).items())),
        "work_group_counts": dict(sorted(Counter(row["work_group"] for row in source_rows).items())),
        "registry_org_counts": dict(sorted(Counter(row["registry_org"] for row in source_rows).items())),
        "exclude_reason_counts": dict(sorted(Counter(row["exclude_reason"] for row in excluded_rows).items())),
        "duplicate_crc32_count": sum(1 for row in unique_rows if int(row["duplicate_source_count"]) > 1),
        "files": {
            "source_inventory": "all_sections_source_inventory_v0.csv",
            "excluded": "all_sections_excluded_v0.csv",
            "run_selection": "all_sections_run_selection_v0.csv",
        },
        "modeling_rules": [
            "The run corpus includes all PDFs for non-UUiR candidate objects in the requested range.",
            "Administrative/non-project documents are excluded by filename/path markers only.",
            "Explorer bundle identity is crc32 -> doc_<crc32> across the shared export root.",
            "Run selection is deduplicated by crc32; object/section linkage remains in source inventory.",
            "Original PDFs are read in place; no staging copy is required for this wide-corpus run.",
        ],
    }
    write_json(output_dir / "non_uuir_all_sections_selection_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build all-sections non-UUiR explorer selection.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start", type=int, default=1400)
    parser.add_argument("--end", type=int, default=1883)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.candidates,
                args.source_root,
                args.export_root,
                args.output_dir,
                args.start,
                args.end,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
