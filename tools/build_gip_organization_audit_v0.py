#!/usr/bin/env python3
"""Build a compact human-review registry of organizations entering GIP control."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_OBJECTS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0"
    r"\gip_control_objects_v0.csv"
)
DEFAULT_SECTIONS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0"
    r"\gip_control_sections_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\gip_organization_audit_expanded_v0"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build(objects_path: Path, sections_path: Path, output_dir: Path) -> dict[str, Any]:
    objects = read_csv(objects_path)
    sections = read_csv(sections_path)
    sections_by_object: Counter[str] = Counter(row["object_id"] for row in sections)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    missing_rows: list[dict[str, str]] = []
    for row in objects:
        organization = row.get("effective_org_canonical", "").strip()
        if organization:
            grouped[organization].append(row)
        else:
            missing_rows.append(row)

    audit_rows: list[dict[str, Any]] = []
    for organization, rows in sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0].casefold()),
    ):
        object_ids = sorted({row["object_id"] for row in rows})
        gips = sorted({row["effective_gip"] for row in rows if row["effective_gip"]})
        sources = Counter(row["effective_org_source"] for row in rows)
        rules = Counter(row["effective_author_rule"] for row in rows)
        manifest_hints = sorted(
            {row["manifest_org_hint"] for row in rows if row["manifest_org_hint"]}
        )
        audit_rows.append(
            {
                "organization_canonical": organization,
                "object_count": len(object_ids),
                "section_count": sum(sections_by_object[object_id] for object_id in object_ids),
                "gip_count": len(gips),
                "gips": "|".join(gips),
                "subcontractor_authored_object_count": sum(
                    row["effective_author_rule"] == "subcontractor_actual_author"
                    for row in rows
                ),
                "org_sources": "|".join(
                    f"{key}:{value}" for key, value in sorted(sources.items())
                ),
                "author_rules": "|".join(
                    f"{key or 'missing'}:{value}" for key, value in sorted(rules.items())
                ),
                "manifest_org_hints": "|".join(manifest_hints),
                "sample_object_ids": "|".join(object_ids[:20]),
                "sample_truncated": len(object_ids) > 20,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "organization_canonical",
        "object_count",
        "section_count",
        "gip_count",
        "gips",
        "subcontractor_authored_object_count",
        "org_sources",
        "author_rules",
        "manifest_org_hints",
        "sample_object_ids",
        "sample_truncated",
    ]
    write_csv(output_dir / "gip_organizations_for_human_review_v0.csv", audit_rows, fields)
    write_csv(
        output_dir / "gip_objects_missing_organization_v0.csv",
        missing_rows,
        list(objects[0]),
    )
    forbidden = [
        row["organization_canonical"]
        for row in audit_rows
        if "центральн" in row["organization_canonical"].casefold()
        or "объединение градостроительных" in row["organization_canonical"].casefold()
    ]
    summary = {
        "schema_version": "gip_organization_audit_v0",
        "organization_count": len(audit_rows),
        "object_count_with_organization": sum(
            int(row["object_count"]) for row in audit_rows
        ),
        "object_count_missing_organization": len(missing_rows),
        "forbidden_false_organizations": forbidden,
        "review_file": str(
            output_dir / "gip_organizations_for_human_review_v0.csv"
        ),
    }
    (output_dir / "gip_organization_audit_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GIP organization audit.")
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.objects, args.sections, args.output_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
