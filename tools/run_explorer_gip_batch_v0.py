#!/usr/bin/env python3
"""Run PDF Structure Explorer parser/exporter for the selected GIP corpus."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SELECTION = Path(
    r"E:\output\DocSpectrum\gip_pdf_selection_v0\gip_pdf_selection_v0.csv"
)
DEFAULT_EXPLORER_BACKEND = Path(r"E:\repos\pdf-structure-explorer\backend")
DEFAULT_STORAGE_DIR = Path(r"E:\output\pdf-structure-explorer\storage")
DEFAULT_EXPORT_DIR = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_RUN_DIR = Path(r"E:\output\DocSpectrum\gip_explorer_batch_v0")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_complete_export(export_dir: Path, document_id: str) -> bool:
    path = export_dir / document_id
    required = {
        "manifest.json",
        "documents.csv",
        "pages.csv",
        "elements.csv",
        "text_segments.csv",
        "tables.csv",
        "table_cells.csv",
    }
    return path.is_dir() and required.issubset(
        {item.name for item in path.iterdir() if item.is_file()}
    )


def run(
    selection_path: Path,
    explorer_backend: Path,
    storage_dir: Path,
    export_dir: Path,
    run_dir: Path,
) -> dict[str, Any]:
    os.environ["PSE_STORAGE_DIR"] = str(storage_dir)
    os.environ["PSE_EXPORT_DIR"] = str(export_dir)
    sys.path.insert(0, str(explorer_backend))

    from app import exporter  # noqa: PLC0415
    from app.store import store  # noqa: PLC0415

    rows = read_csv(selection_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "gip_explorer_batch_status_v0.csv"
    summary_path = run_dir / "gip_explorer_batch_v0.json"
    status_rows: list[dict[str, Any]] = []
    started_at = now()

    for index, row in enumerate(rows, start=1):
        started = time.monotonic()
        document_id = row["expected_document_id"]
        pdf_path = Path(row["staging_path"])
        status: dict[str, Any] = {
            "sequence": index,
            "object_id": row["object_id"],
            "document_id": document_id,
            "crc32": row["crc32"],
            "file_name": row["source_file_name"],
            "source_path": row["analysis_target_pdf"],
            "staging_path": str(pdf_path),
            "page_count": "",
            "status": "pending",
            "processed_pages": 0,
            "elapsed_seconds": 0,
            "export_path": "",
            "error": "",
            "updated_at": now(),
        }
        try:
            if is_complete_export(export_dir, document_id):
                status["status"] = "skipped_existing_export"
                status["export_path"] = str(export_dir / document_id)
            else:
                content = pdf_path.read_bytes()
                document = store.add(row["source_file_name"], content)
                if document.document_id != document_id:
                    raise ValueError(
                        f"CRC/document mismatch: {document.document_id} != {document_id}"
                    )
                status["page_count"] = document.page_count
                status["status"] = "processing"
                status["updated_at"] = now()
                status_rows.append(status.copy())
                write_csv(status_path, status_rows, list(status))

                document.parse()
                status_rows.pop()
                if document.status != "parsed":
                    raise RuntimeError(document.error or "Explorer parse failed")
                path, _files = exporter.export_csv_bundle(document, str(export_dir))
                status["status"] = "exported"
                status["processed_pages"] = document.processed_pages
                status["export_path"] = path
        except Exception as exc:  # noqa: BLE001
            status["status"] = "failed"
            status["error"] = f"{type(exc).__name__}: {exc}"
        status["elapsed_seconds"] = round(time.monotonic() - started, 2)
        status["updated_at"] = now()
        status_rows.append(status)
        write_csv(status_path, status_rows, list(status))

        summary = {
            "schema_version": "gip_explorer_batch_v0",
            "started_at": started_at,
            "updated_at": now(),
            "selection_path": str(selection_path),
            "document_count": len(rows),
            "completed_count": sum(
                item["status"] in {"exported", "skipped_existing_export"}
                for item in status_rows
            ),
            "exported_count": sum(
                item["status"] == "exported" for item in status_rows
            ),
            "skipped_count": sum(
                item["status"] == "skipped_existing_export"
                for item in status_rows
            ),
            "failed_count": sum(
                item["status"] == "failed" for item in status_rows
            ),
            "processed_page_count": sum(
                int(item["processed_pages"] or 0) for item in status_rows
            ),
            "current_object_id": row["object_id"],
            "status_file": str(status_path),
            "export_dir": str(export_dir),
        }
        write_json(summary_path, summary)

    summary["finished_at"] = now()
    summary["run_status"] = (
        "completed" if summary["failed_count"] == 0 else "completed_with_failures"
    )
    write_json(summary_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run explorer batch parsing/export for the GIP corpus."
    )
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument(
        "--explorer-backend",
        type=Path,
        default=DEFAULT_EXPLORER_BACKEND,
    )
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.selection,
                args.explorer_backend,
                args.storage_dir,
                args.export_dir,
                args.run_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
