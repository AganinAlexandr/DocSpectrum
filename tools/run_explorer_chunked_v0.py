#!/usr/bin/env python3
"""Run explorer in disposable child processes with at most 40 PDFs each."""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CHILD_RUNNER = REPO_ROOT / "tools" / "run_explorer_gip_batch_v0.py"
DEFAULT_SELECTION = Path(
    r"E:\output\DocSpectrum\non_uuir_all_sections_selection_1001_1399_v2"
    r"\all_sections_run_selection_without_memory_anomalies_v0.csv"
)
DEFAULT_EXPORT_DIR = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_RUN_DIR = Path(
    r"E:\output\DocSpectrum\non_uuir_all_sections_explorer_1001_1399_chunked_v0"
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


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


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
    return path.is_dir() and REQUIRED_EXPORT_FILES.issubset(
        {item.name for item in path.iterdir() if item.is_file()}
    )


def pending_rows(
    rows: list[dict[str, str]],
    export_dir: Path,
    excluded_document_ids: set[str],
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["expected_document_id"] not in excluded_document_ids
        and not is_complete_export(export_dir, row["expected_document_id"])
    ]


def working_set_bytes(process_id: int) -> int:
    if sys.platform != "win32":
        return 0
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        process_id,
    )
    if not handle:
        return 0
    try:
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        return int(counters.WorkingSetSize) if ok else 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def last_processing_row(status_path: Path) -> dict[str, str] | None:
    if not status_path.is_file():
        return None
    rows = read_csv(status_path)
    processing = [row for row in rows if row.get("status") == "processing"]
    return processing[-1] if processing else None


def run_child(
    command: list[str],
    batch_dir: Path,
    max_working_set_bytes: int,
    timeout_seconds: int,
) -> tuple[str, int, int]:
    batch_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = batch_dir / "child_stdout.log"
    stderr_path = batch_dir / "child_stderr.log"
    started = time.monotonic()
    peak_working_set = 0
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        while True:
            return_code = process.poll()
            current_working_set = working_set_bytes(process.pid)
            peak_working_set = max(peak_working_set, current_working_set)
            if return_code is not None:
                return "completed" if return_code == 0 else "child_failed", return_code, peak_working_set
            if current_working_set > max_working_set_bytes:
                process.kill()
                process.wait()
                return "memory_guard", process.returncode or -1, peak_working_set
            if time.monotonic() - started > timeout_seconds:
                process.kill()
                process.wait()
                return "timeout_guard", process.returncode or -1, peak_working_set
            time.sleep(2)


def run(
    selection_path: Path,
    export_dir: Path,
    run_dir: Path,
    chunk_size: int,
    max_working_set_gb: float,
    timeout_minutes: int,
    max_batches: int,
    dry_run: bool,
) -> dict[str, Any]:
    if not 1 <= chunk_size <= 40:
        raise ValueError("chunk_size must be between 1 and 40")

    rows = read_csv(selection_path)
    run_dir.mkdir(parents=True, exist_ok=True)
    excluded_document_ids: set[str] = set()
    planned_document_ids: set[str] = set()
    anomaly_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    batch_number = 0
    initial_pending_count = len(pending_rows(rows, export_dir, set()))

    while True:
        pending = pending_rows(
            rows,
            export_dir,
            excluded_document_ids | planned_document_ids,
        )
        if not pending or (max_batches and batch_number >= max_batches):
            break
        batch_number += 1
        chunk = pending[:chunk_size]
        batch_dir = run_dir / f"batch_{batch_number:04d}"
        selection_file = batch_dir / "selection.csv"
        write_csv(selection_file, chunk, list(rows[0]))
        if dry_run:
            batch_rows.append(
                {
                    "batch_number": batch_number,
                    "status": "planned",
                    "document_count": len(chunk),
                    "first_document_id": chunk[0]["expected_document_id"],
                    "last_document_id": chunk[-1]["expected_document_id"],
                    "peak_working_set_bytes": 0,
                }
            )
            planned_document_ids.update(row["expected_document_id"] for row in chunk)
            continue

        child_run_dir = batch_dir / "run"
        command = [
            sys.executable,
            str(CHILD_RUNNER),
            "--selection",
            str(selection_file),
            "--export-dir",
            str(export_dir),
            "--run-dir",
            str(child_run_dir),
        ]
        status, return_code, peak_working_set = run_child(
            command,
            batch_dir,
            int(max_working_set_gb * 1024**3),
            timeout_minutes * 60,
        )
        batch_rows.append(
            {
                "batch_number": batch_number,
                "status": status,
                "document_count": len(chunk),
                "first_document_id": chunk[0]["expected_document_id"],
                "last_document_id": chunk[-1]["expected_document_id"],
                "return_code": return_code,
                "peak_working_set_bytes": peak_working_set,
            }
        )
        write_csv(run_dir / "chunked_batches_v0.csv", batch_rows, list(batch_rows[0]))

        if status in {"memory_guard", "timeout_guard"}:
            processing = last_processing_row(
                child_run_dir / "gip_explorer_batch_status_v0.csv"
            )
            if processing is None:
                raise RuntimeError(f"{status} fired without a processing row")
            document_id = processing["document_id"]
            excluded_document_ids.add(document_id)
            anomaly_rows.append(
                {
                    "document_id": document_id,
                    "object_id": processing["object_id"],
                    "file_name": processing["file_name"],
                    "source_path": processing["source_path"],
                    "guard_status": status,
                    "peak_working_set_bytes": peak_working_set,
                    "retry_policy": "manual_single_document_run",
                }
            )
            write_csv(
                run_dir / "explorer_guard_anomalies_v0.csv",
                anomaly_rows,
                list(anomaly_rows[0]),
            )
        elif status != "completed":
            raise RuntimeError(f"Child batch {batch_number} failed: {status}")

    remaining = pending_rows(rows, export_dir, excluded_document_ids)
    summary = {
        "schema_version": "explorer_chunked_v0",
        "updated_at": now(),
        "selection_path": str(selection_path),
        "document_count": len(rows),
        "chunk_size": chunk_size,
        "batch_count": batch_number,
        "guard_anomaly_count": len(anomaly_rows),
        "excluded_document_ids": sorted(excluded_document_ids),
        "initial_pending_document_count": initial_pending_count,
        "planned_document_count": len(planned_document_ids),
        "remaining_document_count": (
            initial_pending_count if dry_run else len(remaining)
        ),
        "complete_export_count": sum(
            is_complete_export(export_dir, row["expected_document_id"])
            for row in rows
        ),
        "dry_run": dry_run,
    }
    write_json(run_dir / "explorer_chunked_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run explorer in disposable chunks of at most 40 PDFs."
    )
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--chunk-size", type=int, default=40)
    parser.add_argument("--max-working-set-gb", type=float, default=6.0)
    parser.add_argument("--timeout-minutes", type=int, default=20)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.selection,
                args.export_dir,
                args.run_dir,
                args.chunk_size,
                args.max_working_set_gb,
                args.timeout_minutes,
                args.max_batches,
                args.dry_run,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
