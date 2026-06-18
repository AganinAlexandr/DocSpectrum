#!/usr/bin/env python3
"""Build a representative-section authorship corpus for an object-id range."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_ROOT = Path(r"E:\MSE_арх")
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\title_authorship_range_1800_1883_v0"
)
DEFAULT_STAGING_DIR = Path(
    r"E:\output\DocSpectrum\title_authorship_range_1800_1883_pdf_input_v0"
)
SECTION_PRIORITY = ("КР", "ПОКР", "ПОС", "АР")
OBJECT_RE = re.compile(r"^(?P<number>\d{4})_25(?:\D|$)")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def crc32_file(path: Path) -> str:
    value = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value = zlib.crc32(chunk, value)
    return f"{value & 0xFFFFFFFF:08x}"


def section_code(path: Path) -> str | None:
    name = path.stem
    if re.search(r"ИУЛ", name, flags=re.IGNORECASE):
        return None
    for code in SECTION_PRIORITY:
        if re.search(
            rf"(?<![А-ЯЁA-Z0-9]){code}(?![А-ЯЁA-Z0-9])",
            name,
            flags=re.IGNORECASE,
        ):
            return code
    return None


def is_pre_expertise(path: Path) -> bool:
    value = str(path).casefold()
    return any(
        marker in value
        for marker in (
            "документация на проверку",
            "документация для проверки",
            "для_проверки",
            "для проверки",
        )
    ) and not any(
        marker in value
        for marker in ("ответы", "заключение", "егрз")
    )


def select_version(paths: list[Path]) -> tuple[Path | None, str]:
    if not paths:
        return None, "not_available"
    by_crc: dict[str, list[Path]] = {}
    for path in sorted(paths):
        by_crc.setdefault(crc32_file(path), []).append(path)
    unique_paths = [items[0] for items in by_crc.values()]
    if len(unique_paths) == 1:
        return unique_paths[0], (
            "single_available"
            if len(paths) == 1
            else "duplicate_identical_content"
        )
    pre_expertise = [path for path in unique_paths if is_pre_expertise(path)]
    if len(pre_expertise) == 1:
        return pre_expertise[0], "pre_expertise_version"
    return None, "ambiguous_multiple_versions"


def object_directories(
    source_root: Path,
    start: int,
    end: int,
) -> dict[int, Path]:
    result = {}
    for path in source_root.iterdir():
        if not path.is_dir():
            continue
        match = OBJECT_RE.match(path.name)
        if not match:
            continue
        number = int(match.group("number"))
        if start <= number <= end:
            result[number] = path
    return result


def build(
    source_root: Path,
    output_dir: Path,
    staging_dir: Path,
    start: int,
    end: int,
) -> dict[str, Any]:
    directories = object_directories(source_root, start, end)
    inventory_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    staging_dir.mkdir(parents=True, exist_ok=True)

    for number in range(start, end + 1):
        object_id = f"{number}_25"
        source_dir = directories.get(number)
        if source_dir is None:
            inventory_rows.append(
                {
                    "object_id": object_id,
                    "source_dir": "",
                    "address": "",
                    "pdf_count": 0,
                    "selected_section_code": "",
                    "selected_pdf": "",
                    "selection_status": "source_directory_missing",
                    "version_rule": "",
                    "candidate_count": 0,
                }
            )
            continue

        pdfs = sorted(source_dir.rglob("*.pdf"))
        by_section = {code: [] for code in SECTION_PRIORITY}
        for pdf in pdfs:
            code = section_code(pdf)
            if code:
                by_section[code].append(pdf)

        selected_code = ""
        selected_path: Path | None = None
        version_rule = ""
        candidate_count = 0
        for code in SECTION_PRIORITY:
            candidates = by_section[code]
            if not candidates:
                continue
            selected_code = code
            candidate_count = len(candidates)
            selected_path, version_rule = select_version(candidates)
            break

        status = (
            "selected"
            if selected_path
            else version_rule
            if selected_code
            else "no_priority_section_pdf"
            if pdfs
            else "no_pdf_files"
        )
        address = source_dir.name[len(object_id) :].strip()
        inventory_rows.append(
            {
                "object_id": object_id,
                "source_dir": str(source_dir),
                "address": address,
                "pdf_count": len(pdfs),
                "selected_section_code": selected_code,
                "selected_pdf": str(selected_path or ""),
                "selection_status": status,
                "version_rule": version_rule,
                "candidate_count": candidate_count,
            }
        )
        if not selected_path:
            continue

        crc32 = crc32_file(selected_path)
        staging_name = f"{object_id}__{selected_code}__{crc32}.pdf"
        staging_path = staging_dir / staging_name
        if not staging_path.exists() or staging_path.stat().st_size != selected_path.stat().st_size:
            shutil.copy2(selected_path, staging_path)
        selection_rows.append(
            {
                "object_id": object_id,
                "source_number": str(number),
                "address": address,
                "section_code": selected_code,
                "authorship_source_pdf": str(selected_path),
                "analysis_target_pdf": str(selected_path),
                "authorship_selection_rule": (
                    f"priority_{selected_code.lower()}|{version_rule}"
                ),
                "source_file_name": selected_path.name,
                "file_size_bytes": selected_path.stat().st_size,
                "crc32": crc32,
                "expected_document_id": f"doc_{crc32}",
                "staging_file_name": staging_name,
                "staging_path": str(staging_path),
                "staging_rule": "range_authorship_staging",
                "version_count": candidate_count,
                "title_extraction_status": "pending_explorer_export",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "object_inventory_v0.csv", inventory_rows)
    if selection_rows:
        write_csv(output_dir / "authorship_selection_v0.csv", selection_rows)
    summary = {
        "schema_version": "title_authorship_range_v0",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "range": f"{start}_25..{end}_25",
        "expected_object_count": end - start + 1,
        "source_directory_count": len(directories),
        "selected_object_count": len(selection_rows),
        "missing_object_count": len(inventory_rows) - len(selection_rows),
        "unique_crc32_count": len({row["crc32"] for row in selection_rows}),
        "section_counts": dict(
            sorted(Counter(row["section_code"] for row in selection_rows).items())
        ),
        "status_counts": dict(
            sorted(Counter(row["selection_status"] for row in inventory_rows).items())
        ),
        "output_dir": str(output_dir),
        "staging_dir": str(staging_dir),
        "files": {
            "inventory": "object_inventory_v0.csv",
            "selection": "authorship_selection_v0.csv",
        },
    }
    (output_dir / "title_authorship_range_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build representative authorship-section corpus by object range."
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING_DIR)
    parser.add_argument("--start", type=int, default=1800)
    parser.add_argument("--end", type=int, default=1883)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.source_root,
                args.output_dir,
                args.staging_dir,
                args.start,
                args.end,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
