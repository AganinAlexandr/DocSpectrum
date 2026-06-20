#!/usr/bin/env python3
"""Merge the 1001-1399 and 1400-1883 GIP-control inputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_MANIFESTS = (
    Path(r"E:\output\DocSpectrum\non_uuir_titled_objects_1001_1399_v0.csv"),
    Path(r"E:\output\DocSpectrum\non_uuir_titled_objects_v0.csv"),
)
DEFAULT_SELECTIONS = (
    Path(
        r"E:\output\DocSpectrum\non_uuir_all_sections_selection_1001_1399_v2"
        r"\all_sections_run_selection_v0.csv"
    ),
    Path(
        r"E:\output\DocSpectrum\non_uuir_all_sections_selection_v0"
        r"\all_sections_run_selection_v0.csv"
    ),
)
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\gip_control_expanded_inputs_v0"
)
REQUIRED_EXPORT_FILES = {
    "manifest.json",
    "documents.csv",
    "pages.csv",
    "elements.csv",
    "text_segments.csv",
    "tables.csv",
    "table_cells.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def complete_bundle(export_root: Path, document_id: str) -> bool:
    path = export_root / document_id
    return path.is_dir() and REQUIRED_EXPORT_FILES.issubset(
        {item.name for item in path.iterdir() if item.is_file()}
    )


def union_fields(rows: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for row in rows:
        for field in row:
            if field not in result:
                result.append(field)
    return result


def build(
    manifests: tuple[Path, ...],
    selections: tuple[Path, ...],
    export_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest_by_object: dict[str, dict[str, str]] = {}
    for path in manifests:
        for row in read_csv(path):
            object_id = row["object_id"]
            if object_id in manifest_by_object:
                raise ValueError(f"Duplicate manifest object: {object_id}")
            manifest_by_object[object_id] = row

    selection_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    seen_object_bundle: set[tuple[str, str]] = set()
    for path in selections:
        for row in read_csv(path):
            key = (row["object_id"], row["expected_document_id"])
            if key in seen_object_bundle:
                continue
            seen_object_bundle.add(key)
            if not complete_bundle(export_root, row["expected_document_id"]):
                excluded_rows.append(
                    {
                        **row,
                        "expanded_exclude_reason": "resource_limit_or_missing_bundle",
                    }
                )
                continue
            selection_rows.append(row)

    manifest_rows = [
        manifest_by_object[object_id] for object_id in sorted(manifest_by_object)
    ]
    selection_rows.sort(
        key=lambda row: (
            row["object_id"],
            row.get("section_code", ""),
            row["expected_document_id"],
        )
    )
    excluded_rows.sort(
        key=lambda row: (row["object_id"], row["expected_document_id"])
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_control_manifest_expanded_v0.csv",
        manifest_rows,
        union_fields(manifest_rows),
    )
    write_csv(
        output_dir / "gip_control_selection_expanded_v0.csv",
        selection_rows,
        union_fields(selection_rows),
    )
    write_csv(
        output_dir / "gip_control_resource_exclusions_v0.csv",
        excluded_rows,
        union_fields(excluded_rows),
    )
    summary = {
        "schema_version": "gip_control_expanded_inputs_v0",
        "manifest_object_count": len(manifest_rows),
        "selection_section_count": len(selection_rows),
        "resource_exclusion_count": len(excluded_rows),
        "manifest_paths": [str(path) for path in manifests],
        "selection_paths": [str(path) for path in selections],
        "export_root": str(export_root),
    }
    (output_dir / "gip_control_expanded_inputs_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build expanded GIP-control inputs.")
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--selection",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                tuple(args.manifest) or DEFAULT_MANIFESTS,
                tuple(args.selection) or DEFAULT_SELECTIONS,
                args.export_root,
                args.output_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
