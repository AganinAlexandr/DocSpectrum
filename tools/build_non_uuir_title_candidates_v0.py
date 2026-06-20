#!/usr/bin/env python3
"""Build a non-UUiR object manifest from title results and the master registry."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from build_cross_org_manifest_v0 import (
    archive_key_from_number,
    find_header_row,
    normalize_header,
    read_xlsx_rows,
)


DEFAULT_TITLE_DOCUMENTS = Path(
    r"E:\output\DocSpectrum\title_authorship_range_1001_1399_results_v0"
    r"\title_authorship_documents_v0.csv"
)
DEFAULT_REGISTRY = Path(r"E:\commons\DocSpectrum\Капремонт_Объекты.xlsx")
DEFAULT_OUTPUT = Path(
    r"E:\output\DocSpectrum\non_uuir_titled_objects_1001_1399_v0.csv"
)
UUIR = "УУиР"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "object_id",
        "address",
        "group",
        "subgroup",
        "gip",
        "org",
        "year",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def registry_by_object_id(path: Path) -> dict[str, dict[str, str]]:
    raw_rows = read_xlsx_rows(path)
    header_index, header_row = find_header_row(raw_rows)
    headers = {
        normalize_header(str(value)): column
        for column, value in header_row.items()
        if column != "_row" and str(value).strip()
    }

    result: dict[str, dict[str, str]] = {}
    for raw in raw_rows[header_index + 1 :]:
        get = lambda name: str(raw.get(headers.get(name, -1), "") or "").strip()
        source_number = get("номер")
        year = get("год")
        if not source_number:
            continue
        object_id = archive_key_from_number(source_number, year)
        if not re.fullmatch(r"\d{4}_\d{2}", object_id):
            continue
        result[object_id] = {
            "address": get("название"),
            "group": get("группа"),
            "subgroup": get("подгруппа"),
            "gip": get("гип"),
            "org": get("проектировщик"),
            "year": year,
        }
    return result


def build(
    title_documents: Path,
    registry_xlsx: Path,
    output_path: Path,
) -> dict[str, Any]:
    title_rows = read_csv(title_documents)
    registry = registry_by_object_id(registry_xlsx)
    rows: list[dict[str, str]] = []
    missing_registry: list[str] = []
    excluded_uuiR: list[str] = []

    for title_row in title_rows:
        object_id = title_row["object_id"].strip()
        metadata = registry.get(object_id)
        if metadata is None:
            missing_registry.append(object_id)
            continue
        if metadata["group"] == UUIR or metadata["subgroup"] == UUIR:
            excluded_uuiR.append(object_id)
            continue
        rows.append({"object_id": object_id, **metadata})

    rows.sort(key=lambda row: row["object_id"])
    write_csv(output_path, rows)
    return {
        "title_document_count": len(title_rows),
        "registry_matched_count": len(title_rows) - len(missing_registry),
        "non_uuir_object_count": len(rows),
        "excluded_uuiR_object_count": len(excluded_uuiR),
        "missing_registry_count": len(missing_registry),
        "group_counts": dict(sorted(Counter(row["group"] for row in rows).items())),
        "output_path": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build non-UUiR candidates from title results and registry."
    )
    parser.add_argument("--title-documents", type=Path, default=DEFAULT_TITLE_DOCUMENTS)
    parser.add_argument("--registry-xlsx", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.title_documents, args.registry_xlsx, args.output),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
