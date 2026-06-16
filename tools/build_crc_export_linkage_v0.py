from __future__ import annotations

import argparse
import csv
import json
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST_CSV = Path(r"E:\output\DocSpectrum\cross_org_manifest_v0\cross_org_manifest_v0.csv")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\DocSpectrum\export_nk_34")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\crc_export_linkage_nk_34")


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


def crc32_file(path: Path) -> str:
    value = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value = zlib.crc32(chunk, value)
    return f"{value & 0xFFFFFFFF:08X}"


def filter_manifest_rows(
    rows: list[dict[str, str]],
    designer: str,
    corpus_role: str,
) -> list[dict[str, str]]:
    filtered = rows
    if corpus_role:
        filtered = [row for row in filtered if row.get("corpus_role") == corpus_role]
    if designer:
        filtered = [row for row in filtered if row.get("designer") == designer]
    return filtered


def collect_source_pdfs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    source_rows = []
    for row in rows:
        source_dir = Path(row.get("source_dir", ""))
        if not source_dir.exists():
            continue
        for pdf_path in sorted(source_dir.rglob("*.pdf")):
            try:
                crc32 = crc32_file(pdf_path)
                source_rows.append(
                    {
                        "object_id": row.get("object_id", ""),
                        "source_number": row.get("source_number", ""),
                        "year": row.get("year", ""),
                        "designer": row.get("designer", ""),
                        "gip": row.get("gip", ""),
                        "address_normalized": row.get("address_normalized", ""),
                        "work_group": row.get("work_group", ""),
                        "work_subgroup": row.get("work_subgroup", ""),
                        "source_dir": row.get("source_dir", ""),
                        "source_pdf_path": str(pdf_path),
                        "source_pdf_name": pdf_path.name,
                        "source_pdf_size_bytes": pdf_path.stat().st_size,
                        "crc32": crc32,
                        "expected_doc_dir": f"doc_{crc32.lower()}",
                    }
                )
            except OSError as exc:
                source_rows.append(
                    {
                        "object_id": row.get("object_id", ""),
                        "source_number": row.get("source_number", ""),
                        "year": row.get("year", ""),
                        "designer": row.get("designer", ""),
                        "gip": row.get("gip", ""),
                        "address_normalized": row.get("address_normalized", ""),
                        "work_group": row.get("work_group", ""),
                        "work_subgroup": row.get("work_subgroup", ""),
                        "source_dir": row.get("source_dir", ""),
                        "source_pdf_path": str(pdf_path),
                        "source_pdf_name": pdf_path.name,
                        "source_pdf_size_bytes": "",
                        "crc32": "",
                        "expected_doc_dir": "",
                        "error": str(exc),
                    }
                )
    return source_rows


def collect_export_docs(export_root: Path) -> list[dict[str, Any]]:
    rows = []
    for doc_dir in sorted(export_root.glob("doc_*")):
        documents_csv = doc_dir / "documents.csv"
        if not documents_csv.exists():
            continue
        for row in read_csv(documents_csv):
            crc32 = (row.get("file_crc32") or "").upper()
            rows.append(
                {
                    "export_document_id": row.get("document_id", doc_dir.name),
                    "export_doc_dir": doc_dir.name,
                    "export_doc_path": str(doc_dir),
                    "export_file_name": row.get("file_name", ""),
                    "export_file_crc32": crc32,
                    "export_file_size_bytes": row.get("file_size_bytes", ""),
                    "export_page_count": row.get("page_count", ""),
                    "export_parse_status": row.get("parse_status", ""),
                    "export_expected_doc_dir": f"doc_{crc32.lower()}" if crc32 else "",
                    "export_doc_dir_matches_crc32": doc_dir.name == f"doc_{crc32.lower()}" if crc32 else False,
                }
            )
    return rows


def build_linkage_rows(
    source_rows: list[dict[str, Any]],
    export_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_by_crc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    export_by_crc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        if row.get("crc32"):
            source_by_crc[str(row["crc32"])].append(row)
    for row in export_rows:
        if row.get("export_file_crc32"):
            export_by_crc[str(row["export_file_crc32"])].append(row)

    rows = []
    for crc32 in sorted(set(source_by_crc) | set(export_by_crc)):
        sources = source_by_crc.get(crc32, [])
        exports = export_by_crc.get(crc32, [])
        if sources and exports:
            for source in sources:
                for export in exports:
                    rows.append(
                        {
                            **source,
                            **export,
                            "link_status": "matched",
                            "source_match_count": len(sources),
                            "export_match_count": len(exports),
                        }
                    )
        elif sources:
            for source in sources:
                rows.append(
                    {
                        **source,
                        "export_document_id": "",
                        "export_doc_dir": "",
                        "export_doc_path": "",
                        "export_file_name": "",
                        "export_file_crc32": "",
                        "export_file_size_bytes": "",
                        "export_page_count": "",
                        "export_parse_status": "",
                        "export_expected_doc_dir": "",
                        "export_doc_dir_matches_crc32": "",
                        "link_status": "source_only",
                        "source_match_count": len(sources),
                        "export_match_count": 0,
                    }
                )
        else:
            for export in exports:
                rows.append(
                    {
                        "object_id": "",
                        "source_number": "",
                        "year": "",
                        "designer": "",
                        "gip": "",
                        "address_normalized": "",
                        "work_group": "",
                        "work_subgroup": "",
                        "source_dir": "",
                        "source_pdf_path": "",
                        "source_pdf_name": "",
                        "source_pdf_size_bytes": "",
                        "crc32": crc32,
                        "expected_doc_dir": f"doc_{crc32.lower()}",
                        **export,
                        "link_status": "export_only",
                        "source_match_count": 0,
                        "export_match_count": len(exports),
                    }
                )
    rows.sort(key=lambda row: (row["link_status"], row["object_id"], row["crc32"], row["export_doc_dir"]))
    return rows


def build(
    manifest_csv: Path,
    export_root: Path,
    output_dir: Path,
    designer: str,
    corpus_role: str,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest_rows = filter_manifest_rows(read_csv(manifest_csv), designer, corpus_role)
    source_rows = collect_source_pdfs(manifest_rows)
    export_rows = collect_export_docs(export_root)
    linkage_rows = build_linkage_rows(source_rows, export_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    source_fields = [
        "object_id",
        "source_number",
        "year",
        "designer",
        "gip",
        "address_normalized",
        "work_group",
        "work_subgroup",
        "source_dir",
        "source_pdf_path",
        "source_pdf_name",
        "source_pdf_size_bytes",
        "crc32",
        "expected_doc_dir",
    ]
    export_fields = [
        "export_document_id",
        "export_doc_dir",
        "export_doc_path",
        "export_file_name",
        "export_file_crc32",
        "export_file_size_bytes",
        "export_page_count",
        "export_parse_status",
        "export_expected_doc_dir",
        "export_doc_dir_matches_crc32",
    ]
    linkage_fields = source_fields + export_fields + ["link_status", "source_match_count", "export_match_count"]
    write_csv(output_dir / "source_pdf_crc_v0.csv", source_rows, source_fields)
    write_csv(output_dir / "export_documents_crc_v0.csv", export_rows, export_fields)
    write_csv(output_dir / "doc_crc_linkage_v0.csv", linkage_rows, linkage_fields)

    matched = [row for row in linkage_rows if row["link_status"] == "matched"]
    summary = {
        "schema_version": "doc_crc_linkage_v0",
        "generated_at": generated_at,
        "manifest_csv": str(manifest_csv),
        "export_root": str(export_root),
        "output_dir": str(output_dir),
        "designer_filter": designer,
        "corpus_role_filter": corpus_role,
        "manifest_object_count": len({row["object_id"] for row in manifest_rows}),
        "source_pdf_count": len(source_rows),
        "source_unique_crc32_count": len({row["crc32"] for row in source_rows if row.get("crc32")}),
        "export_document_count": len(export_rows),
        "export_unique_crc32_count": len({row["export_file_crc32"] for row in export_rows if row.get("export_file_crc32")}),
        "link_status_counts": dict(Counter(row["link_status"] for row in linkage_rows)),
        "matched_export_document_count": len({row["export_doc_dir"] for row in matched}),
        "matched_object_count": len({row["object_id"] for row in matched}),
        "objects_without_matched_exports": sorted(
            {row["object_id"] for row in manifest_rows}
            - {row["object_id"] for row in matched if row.get("object_id")}
        ),
        "export_doc_dir_crc_mismatch_count": sum(
            1 for row in export_rows if str(row["export_doc_dir_matches_crc32"]).lower() != "true"
        ),
        "modeling_rules": [
            "Canonical explorer bundle linkage is source PDF crc32 -> doc_<lower(crc32)>.",
            "crc32 must be computed from the original source PDF, not inferred from file name.",
            "After resolving a doc_<crc32> export folder, verify documents.csv file_crc32 and file_name.",
            "Object/domain identity comes from the project manifest; explorer doc_<crc32> is a document/bundle identity.",
        ],
        "files": {
            "source_pdf_crc": "source_pdf_crc_v0.csv",
            "export_documents_crc": "export_documents_crc_v0.csv",
            "doc_crc_linkage": "doc_crc_linkage_v0.csv",
        },
    }
    write_json(output_dir / "doc_crc_linkage_v0.json", summary)

    readme = f"""# doc_crc_linkage_v0

CRC32 linkage between source PDFs and `pdf-structure-explorer` exports.

Generated at:

- `{generated_at}`

Canonical rule:

- compute CRC32 from the original source PDF;
- resolve explorer bundle as `doc_<lower(crc32)>`;
- verify `documents.csv.file_crc32` and `documents.csv.file_name`;
- keep `object_id` from the project manifest, not from the explorer bundle name.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build crc32 linkage between source PDFs and explorer doc_<crc32> exports.")
    parser.add_argument("--manifest-csv", type=Path, default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--designer", default="", help="Optional designer filter from cross_org_manifest_v0.csv.")
    parser.add_argument("--corpus-role", default="cross_org_candidate")
    args = parser.parse_args()
    build(args.manifest_csv, args.export_root, args.output_dir, args.designer, args.corpus_role)


if __name__ == "__main__":
    main()
