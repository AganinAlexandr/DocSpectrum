#!/usr/bin/env python3
"""Select canonical analysis and prioritized authorship PDFs for GIP extraction."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OBJECTS = Path(
    r"E:\output\DocSpectrum\gip_priority_manifest_v0\gip_priority_objects_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_pdf_selection_v0")
DEFAULT_ANALYSIS_STAGING_DIR = Path(
    r"E:\output\DocSpectrum\gip_priority_analysis_pdf_input_v0"
)
DEFAULT_AUTHORSHIP_STAGING_DIR = Path(
    r"E:\output\DocSpectrum\gip_priority_authorship_pdf_input_v0"
)
AUTHORSHIP_PRIORITY = ("КР", "ПОС", "АР")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def crc32_file(path: Path) -> str:
    value = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value = zlib.crc32(chunk, value)
    return f"{value & 0xFFFFFFFF:08x}"


def is_target_kr(path: Path) -> bool:
    return section_code(path) == "КР"


def section_code(path: Path) -> str | None:
    name = path.stem
    if re.search(r"ИУЛ", name, flags=re.IGNORECASE):
        return None
    patterns = (
        ("ПОС", ("ПОС", "ПОКР")),
        ("АР", ("АР",)),
        ("КР", ("КР",)),
    )
    for code, markers in patterns:
        if any(
            re.search(
                rf"(^|[\s._№-]){marker}($|[\s._№-])",
                name,
                flags=re.IGNORECASE,
            )
            for marker in markers
        ):
            return code
    return None


def select_analysis_pdf(paths: list[Path]) -> tuple[Path, str]:
    if len(paths) == 1:
        return paths[0], "single_available"
    pre_expertise = [
        path
        for path in paths
        if "документация на проверку" in str(path).casefold()
    ]
    if len(pre_expertise) == 1:
        return pre_expertise[0], "pre_expertise_version"
    raise ValueError(
        "Cannot choose canonical analysis PDF: "
        + " | ".join(str(path) for path in paths)
    )


def select_authorship_section(
    section_paths: dict[str, list[Path]],
) -> tuple[str, Path, str]:
    for code in AUTHORSHIP_PRIORITY:
        paths = sorted(section_paths.get(code, []))
        if paths:
            selected, version_rule = select_analysis_pdf(paths)
            return code, selected, f"priority_{code.lower()}|{version_rule}"
    raise ValueError("No authorship source section found (КР/ПОС/АР)")


def build(
    objects_path: Path,
    output_dir: Path,
    analysis_staging_dir: Path,
    authorship_staging_dir: Path,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    objects = read_csv(objects_path)
    selections: list[dict[str, Any]] = []
    authorship_selections: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []
    analysis_staging_dir.mkdir(parents=True, exist_ok=True)
    authorship_staging_dir.mkdir(parents=True, exist_ok=True)

    for row in objects:
        source_dir = Path(row["source_dir"])
        section_paths: dict[str, list[Path]] = {
            code: [] for code in AUTHORSHIP_PRIORITY
        }
        for path in source_dir.rglob("*.pdf"):
            code = section_code(path)
            if code:
                section_paths[code].append(path)
        target_paths = sorted(section_paths["КР"])
        if not target_paths:
            raise ValueError(f"No target KR PDF for {row['object_id']}")
        selected, rule = select_analysis_pdf(target_paths)
        selected_crc = crc32_file(selected)
        staging_name = f"{row['object_id']}__KR__{selected_crc}.pdf"
        staging_path = analysis_staging_dir / staging_name
        shutil.copy2(selected, staging_path)

        authorship_code, authorship_selected, authorship_rule = (
            select_authorship_section(section_paths)
        )
        authorship_crc = crc32_file(authorship_selected)
        if authorship_selected == selected:
            authorship_staging_name = staging_name
            authorship_staging_path = staging_path
            authorship_staging_rule = "reuse_analysis_staging"
        else:
            authorship_staging_name = (
                f"{row['object_id']}__{authorship_code}__{authorship_crc}.pdf"
            )
            authorship_staging_path = (
                authorship_staging_dir / authorship_staging_name
            )
            shutil.copy2(authorship_selected, authorship_staging_path)
            authorship_staging_rule = "fallback_authorship_staging"
        authorship_selections.append(
            {
                "object_id": row["object_id"],
                "source_number": row["source_number"],
                "address": row["address"],
                "section_code": authorship_code,
                "authorship_source_pdf": str(authorship_selected),
                "authorship_selection_rule": authorship_rule,
                "source_file_name": authorship_selected.name,
                "file_size_bytes": authorship_selected.stat().st_size,
                "crc32": authorship_crc,
                "expected_document_id": f"doc_{authorship_crc}",
                "staging_file_name": authorship_staging_name,
                "staging_path": str(authorship_staging_path),
                "staging_rule": authorship_staging_rule,
                "version_count": len(section_paths[authorship_code]),
                "title_extraction_status": "pending_explorer_export",
            }
        )

        for code, paths in section_paths.items():
            for path in sorted(paths):
                crc32 = crc32_file(path)
                versions.append(
                    {
                        "object_id": row["object_id"],
                        "section_code": code,
                        "source_path": str(path),
                        "file_name": path.name,
                        "file_size_bytes": path.stat().st_size,
                        "last_write_time": datetime.fromtimestamp(
                            path.stat().st_mtime,
                            timezone.utc,
                        ).isoformat(),
                        "crc32": crc32,
                        "is_selected_analysis_target": (
                            code == "КР" and path == selected
                        ),
                        "is_selected_authorship_source": (
                            path == authorship_selected
                        ),
                        "version_role": (
                            "single_available"
                            if len(paths) == 1
                            else "pre_expertise"
                            if "документация на проверку"
                            in str(path).casefold()
                            else "post_submission_or_expertise"
                        ),
                    }
                )

        selections.append(
            {
                "object_id": row["object_id"],
                "source_number": row["source_number"],
                "address": row["address"],
                "expected_gip_human": row["expected_gip_human"],
                "expected_org_human": row["expected_org_human"],
                "expected_work_type_human": row["expected_work_type_human"],
                "analysis_target_section": "КР",
                "analysis_target_pdf": str(selected),
                "analysis_selection_rule": rule,
                "source_file_name": selected.name,
                "file_size_bytes": selected.stat().st_size,
                "crc32": selected_crc,
                "expected_document_id": f"doc_{selected_crc}",
                "staging_file_name": staging_name,
                "staging_path": str(staging_path),
                "version_count": len(target_paths),
                "title_extraction_status": "pending_explorer_export",
            }
        )

    write_csv(
        output_dir / "gip_pdf_selection_v0.csv",
        selections,
        list(selections[0]),
    )
    write_csv(
        output_dir / "gip_authorship_pdf_selection_v0.csv",
        authorship_selections,
        list(authorship_selections[0]),
    )
    write_csv(
        output_dir / "gip_pdf_versions_v0.csv",
        versions,
        list(versions[0]),
    )
    summary = {
        "schema_version": "gip_pdf_selection_v0",
        "generated_at": generated_at,
        "selected_object_count": len(selections),
        "selected_pdf_count": len(selections),
        "unique_crc32_count": len({row["crc32"] for row in selections}),
        "analysis_staging_dir": str(analysis_staging_dir),
        "authorship_selected_pdf_count": len(authorship_selections),
        "authorship_unique_crc32_count": len(
            {row["crc32"] for row in authorship_selections}
        ),
        "authorship_section_counts": {
            code: sum(
                row["section_code"] == code for row in authorship_selections
            )
            for code in AUTHORSHIP_PRIORITY
        },
        "authorship_staging_dir": str(authorship_staging_dir),
        "authorship_reuses_analysis_count": sum(
            row["staging_rule"] == "reuse_analysis_staging"
            for row in authorship_selections
        ),
        "authorship_fallback_staging_count": sum(
            row["staging_rule"] == "fallback_authorship_staging"
            for row in authorship_selections
        ),
        "multi_version_object_count": len(
            {row["object_id"] for row in selections if row["version_count"] > 1}
        ),
        "multi_version_objects": sorted(
            {row["object_id"] for row in selections if row["version_count"] > 1}
        ),
        "selection_rule_counts": {
            rule: sum(row["analysis_selection_rule"] == rule for row in selections)
            for rule in sorted({row["analysis_selection_rule"] for row in selections})
        },
        "rules": [
            "analysis target is the KR section for all factor-test objects.",
            "authorship source priority is KR, then POKR/POS, then AR.",
            "all organization/GIP parties on the selected title pages are retained.",
            "multi-version objects use the pre-expertise KR for factor comparability.",
            "all discovered candidate versions remain in a separate inventory.",
            "staging copies preserve source files and are keyed by object_id and crc32.",
        ],
        "files": {
            "selection": "gip_pdf_selection_v0.csv",
            "authorship_selection": "gip_authorship_pdf_selection_v0.csv",
            "versions": "gip_pdf_versions_v0.csv",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gip_pdf_selection_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select GIP analysis PDFs and build explorer staging copies."
    )
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--analysis-staging-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_STAGING_DIR,
    )
    parser.add_argument(
        "--authorship-staging-dir",
        type=Path,
        default=DEFAULT_AUTHORSHIP_STAGING_DIR,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.objects,
                args.output_dir,
                args.analysis_staging_dir,
                args.authorship_staging_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
