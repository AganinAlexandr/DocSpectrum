#!/usr/bin/env python3
"""Compare planned GIP experiment labels with title-page extraction."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from text_features import normalize_text


DEFAULT_MEMBERSHIPS = Path(
    r"E:\output\DocSpectrum\gip_priority_manifest_v0"
    r"\gip_priority_memberships_v0.csv"
)
DEFAULT_PARTIES = Path(
    r"E:\output\DocSpectrum\title_authorship_v0"
    r"\title_authorship_parties_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_reconciliation_v0")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def identity_text(value: str) -> str:
    value = normalize_text(value)
    return " ".join(re.findall(r"[а-яa-z0-9]+", value))


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def compare_gip(expected: str, extracted: str) -> str:
    expected_key = identity_text(expected)
    extracted_key = identity_text(extracted)
    if not expected_key:
        return "no_planned_label"
    if not extracted_key:
        return "title_not_extracted"
    if expected_key == extracted_key:
        return "exact_match"
    if edit_distance(expected_key, extracted_key) <= 1:
        return "ocr_near_match"
    return "source_conflict"


def compare_org(expected: str, extracted: str) -> str:
    expected_key = identity_text(expected).replace(" ", "")
    extracted_key = identity_text(extracted).replace(" ", "")
    if not expected_key:
        return "no_planned_label"
    aliases = {
        "строймонтаж": "строймонтаж",
        "строймонтажсп": "строймонтаж",
        "спстройинвестгрупп": "стройинвест",
        "стройинвест": "стройинвест",
        "скгамма": "гамма",
    }
    expected_key = re.sub(r"^(?:ооо|000|ао|пао|оао|зао)", "", expected_key)
    extracted_key = re.sub(r"^(?:ооо|000|ао|пао|оао|зао)", "", extracted_key)
    expected_key = aliases.get(expected_key, expected_key)
    extracted_key = aliases.get(extracted_key, extracted_key)
    if expected_key in extracted_key or extracted_key in expected_key:
        return "match"
    return "source_conflict"


def collapse_memberships(
    memberships: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in memberships:
        grouped.setdefault(row["object_id"], []).append(row)
    result = {}
    for object_id, rows in grouped.items():
        expected_gips = sorted(
            {row["expected_gip_human"] for row in rows if row["expected_gip_human"]}
        )
        expected_orgs = sorted(
            {
                row["expected_org_human"] or row["registry_org"]
                for row in rows
                if row["expected_org_human"] or row["registry_org"]
            }
        )
        result[object_id] = {
            "expected_gip_human": ";".join(expected_gips),
            "expected_org_human": ";".join(expected_orgs),
            "experiment_schemes": ";".join(
                sorted({row["scheme"] for row in rows})
            ),
        }
    return result


def build(
    memberships_path: Path,
    parties_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    expected = collapse_memberships(read_csv(memberships_path))
    parties = {
        row["object_id"]: row
        for row in read_csv(parties_path)
        if row["effective_author"].lower() == "true"
    }
    rows = []
    for object_id in sorted(expected):
        planned = expected[object_id]
        party = parties.get(object_id, {})
        title_gip = party.get("gip_surname_normalized", "")
        title_org = party.get("organization_name_raw", "")
        gip_status = compare_gip(
            planned["expected_gip_human"],
            title_gip,
        )
        org_status = compare_org(
            planned["expected_org_human"],
            title_org,
        )
        resolution = (
            "accepted_title_evidence"
            if gip_status in {"exact_match", "ocr_near_match"}
            and org_status in {"match", "no_planned_label"}
            else "owner_review_required"
        )
        rows.append(
            {
                "object_id": object_id,
                **planned,
                "title_gip_raw": party.get("gip_name_raw", ""),
                "title_gip_normalized": title_gip,
                "title_organization": title_org,
                "title_organization_evidence": party.get(
                    "organization_evidence_text",
                    "",
                ),
                "gip_comparison_status": gip_status,
                "organization_comparison_status": org_status,
                "resolution_status": resolution,
                "title_extraction_confidence": party.get(
                    "extraction_confidence",
                    "",
                ),
                "rule": (
                    "title evidence is retained; planned labels are never "
                    "silently overwritten"
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "gip_reconciliation_v0.csv", rows)
    summary = {
        "schema_version": "gip_reconciliation_v0",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "object_count": len(rows),
        "gip_status_counts": dict(
            sorted(Counter(row["gip_comparison_status"] for row in rows).items())
        ),
        "organization_status_counts": dict(
            sorted(
                Counter(
                    row["organization_comparison_status"] for row in rows
                ).items()
            )
        ),
        "resolution_status_counts": dict(
            sorted(Counter(row["resolution_status"] for row in rows).items())
        ),
        "file": "gip_reconciliation_v0.csv",
    }
    (output_dir / "gip_reconciliation_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile planned GIP labels with title evidence."
    )
    parser.add_argument("--memberships", type=Path, default=DEFAULT_MEMBERSHIPS)
    parser.add_argument("--parties", type=Path, default=DEFAULT_PARTIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.memberships, args.parties, args.output_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
