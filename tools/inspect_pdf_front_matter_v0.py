#!/usr/bin/env python3
"""Inspect first-page text for unresolved PDF corpus entries."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from text_features import normalize_text


DEFAULT_SELECTION = Path(
    r"E:\output\DocSpectrum\non_uuir_all_sections_selection_1001_1399_v0"
    r"\all_sections_run_selection_v0.csv"
)
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\front_matter_review_1001_1399_v0"
)

INTEREST_RE = re.compile(
    r"\b(?:проектная документация|раздел|подраздел|договор|"
    r"техническ\w*\s+паспорт|иная документация|локальн\w*\s+смет|"
    r"пояснительн\w*\s+записк|проект\s+организации)\b",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def bundle_text(bundle: Path, max_pages: int) -> tuple[str, str]:
    text_path = bundle / "text_segments.csv"
    if not text_path.is_file():
        return "", ""
    rows = [
        row
        for row in read_csv(text_path)
        if int(row.get("page_number") or 0) <= max_pages
    ]
    text = "\n".join(row.get("text_value", "") for row in rows)
    return text, "explorer_text_segments"


def pdf_text(path: Path, max_pages: int) -> tuple[str, str]:
    import fitz

    document = fitz.open(path)
    try:
        text = "\n".join(
            document[index].get_text("text")
            for index in range(min(max_pages, document.page_count))
        )
    finally:
        document.close()
    return text, "pymupdf"


def evidence_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        cleaned = " ".join(raw.split())
        if cleaned and INTEREST_RE.search(normalize_text(cleaned)):
            lines.append(cleaned)
    return list(dict.fromkeys(lines))[:20]


def build(
    selection_path: Path,
    export_root: Path,
    output_dir: Path,
    max_pages: int,
) -> dict[str, Any]:
    rows = [
        row
        for row in read_csv(selection_path)
        if row.get("section_code") == "UNKNOWN"
    ]
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        bundle = export_root / row["expected_document_id"]
        text, source = bundle_text(bundle, max_pages)
        if not text.strip():
            text, source = pdf_text(Path(row["analysis_target_pdf"]), max_pages)
        evidence = evidence_lines(text)
        output_rows.append(
            {
                "object_id": row["object_id"],
                "source_pdf_name": row["source_file_name"],
                "source_pdf_path": row["analysis_target_pdf"],
                "expected_document_id": row["expected_document_id"],
                "front_text_source": source,
                "front_text_status": "evidence_found" if evidence else "no_marker_found",
                "evidence_lines": " | ".join(evidence),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "front_matter_review_v0.csv", output_rows)
    summary = {
        "document_count": len(output_rows),
        "status_counts": dict(
            sorted(Counter(row["front_text_status"] for row in output_rows).items())
        ),
        "source_counts": dict(
            sorted(Counter(row["front_text_source"] for row in output_rows).items())
        ),
        "max_pages": max_pages,
        "output": str(output_dir / "front_matter_review_v0.csv"),
    }
    (output_dir / "front_matter_review_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect unresolved PDF front matter.")
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-pages", type=int, default=4)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.selection, args.export_root, args.output_dir, args.max_pages),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
