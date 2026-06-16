from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LINKAGE_CSV = Path(r"E:\output\DocSpectrum\crc_export_linkage_nk_34\doc_crc_linkage_v0.csv")
DEFAULT_OUTPUT_ROOT = Path(r"E:\output\DocSpectrum\export_nk_34_object_view")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def link_or_copy_file(source: Path, target: Path, overwrite: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not overwrite:
            return "exists"
        target.unlink()
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def materialize(linkage_csv: Path, output_root: Path, overwrite: bool) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = [row for row in read_csv(linkage_csv) if row.get("link_status") == "matched"]
    operation_counts: Counter[str] = Counter()
    materialized = []

    for row in rows:
        object_id = row["object_id"]
        bundle_id = row["export_doc_dir"]
        source_dir = Path(row["export_doc_path"])
        target_dir = output_root / object_id / bundle_id
        for source_file in sorted(source_dir.iterdir()):
            if not source_file.is_file():
                continue
            operation = link_or_copy_file(source_file, target_dir / source_file.name, overwrite)
            operation_counts[operation] += 1
        materialized.append(
            {
                "object_id": object_id,
                "bundle_id": bundle_id,
                "crc32": row["crc32"],
                "source_dir": str(source_dir),
                "target_dir": str(target_dir),
                "file_name": row["source_pdf_name"],
            }
        )

    summary = {
        "schema_version": "export_object_view_v0",
        "generated_at": generated_at,
        "linkage_csv": str(linkage_csv),
        "output_root": str(output_root),
        "matched_linkage_rows": len(rows),
        "materialized_bundle_count": len(materialized),
        "object_count": len({row["object_id"] for row in materialized}),
        "operation_counts": dict(operation_counts),
        "modeling_rules": [
            "This is a filesystem compatibility view for older DocSpectrum tools.",
            "Canonical identity remains source PDF crc32 -> doc_<lower(crc32)>.",
            "object_id comes from the project manifest and is used only as the grouping parent.",
        ],
    }
    write_json(output_root / "export_object_view_v0.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize object_id/doc_<crc32> export view from CRC linkage CSV.")
    parser.add_argument("--linkage-csv", type=Path, default=DEFAULT_LINKAGE_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    materialize(args.linkage_csv, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
