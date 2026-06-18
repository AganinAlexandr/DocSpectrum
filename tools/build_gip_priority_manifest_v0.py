#!/usr/bin/env python3
"""Build the prioritized GIP corpus manifest from the human-approved design."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = Path(r"E:\output\DocSpectrum\gip_corpus_candidates_v0.csv")
DEFAULT_SOURCE_ROOT = Path(r"E:\MSE_арх")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_priority_manifest_v0")


def cohort(
    scheme: str,
    cell: str,
    expected_gip: str,
    expected_org: str,
    work_type: str,
    numbers: str,
) -> list[dict[str, str]]:
    return [
        {
            "scheme": scheme,
            "experiment_cell": cell,
            "source_number": number,
            "expected_gip_human": expected_gip,
            "expected_org_human": expected_org,
            "expected_work_type_human": work_type,
        }
        for number in numbers.split()
    ]


MEMBERSHIPS = (
    cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|скатная|Локтев",
        "Локтев",
        "СтройМонтаж",
        "скатная",
        "169425 169725 169825 175225 177825 182325 182525 184725 184825 184925 187125 187925 188025",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|скатная|Ефимов",
        "Ефимов",
        "СтройМонтаж",
        "скатная",
        "169025 170025 170125 170725 171225",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|скатная|Бородин",
        "Бородин",
        "СтройМонтаж",
        "скатная",
        "166725 166825 167825",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|плоская|Бородин",
        "Бородин",
        "СтройМонтаж",
        "плоская",
        "187325 187425 187525 187625",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|плоская|Локтев",
        "Локтев",
        "СтройМонтаж",
        "плоская",
        "142125 187225 188125",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|плоская|Ефимов",
        "Ефимов",
        "СтройМонтаж",
        "плоская",
        "183125 185725 186325",
    )
    + cohort(
        "scheme1_fixed_org_worktype_vary_gip",
        "СтройМонтаж|плоская|Шевченко",
        "Шевченко",
        "СтройМонтаж",
        "плоская",
        "169225",
    )
    + cohort(
        "scheme_cross_org_fixed_gip_worktype",
        "Сергеев|плоская|Ватага",
        "Сергеев",
        "Ватага",
        "плоская",
        "166925 167025",
    )
    + cohort(
        "scheme_cross_org_fixed_gip_worktype",
        "Сергеев|плоская|Гамма",
        "Сергеев",
        "Гамма",
        "плоская",
        "169925",
    )
    + cohort(
        "scheme_cross_org_fixed_gip_worktype",
        "Сергеев|плоская|Стройинвест",
        "Сергеев",
        "Стройинвест",
        "плоская",
        "164625",
    )
    + cohort(
        "scheme_cross_org_fixed_gip_worktype",
        "Сергеев|скатная|Ватага",
        "Сергеев",
        "Ватага",
        "скатная",
        "164825 170225",
    )
    + cohort(
        "scheme_cross_org_fixed_gip_worktype",
        "Сергеев|скатная|Стройинвест",
        "Сергеев",
        "Стройинвест",
        "скатная",
        "146825 164325 164425 165325",
    )
    + cohort(
        "scheme2_fixed_gip_vary_worktype",
        "Сергеев|скатная",
        "Сергеев",
        "",
        "скатная",
        "164825 170225 146825 164325 164425 165325",
    )
    + cohort(
        "scheme2_fixed_gip_vary_worktype",
        "Сергеев|плоская",
        "Сергеев",
        "",
        "плоская",
        "166925 167025 169925 164625",
    )
    + cohort(
        "scheme2_fixed_gip_vary_worktype",
        "Сергеев|фасад",
        "Сергеев",
        "",
        "фасад",
        "159225 169525",
    )
    + cohort(
        "scheme2_fixed_gip_vary_worktype",
        "Сергеев|балконы",
        "Сергеев",
        "",
        "балконы",
        "170425",
    )
    + cohort(
        "scheme2_fixed_gip_vary_worktype",
        "Сергеев|фундамент",
        "Сергеев",
        "",
        "фундамент",
        "140125",
    )
)


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def archive_key(source_number: str) -> str:
    return f"{source_number[:4]}_{source_number[4:]}"


def normalize_work_type(value: str) -> str:
    return value.strip().strip("/\\_").casefold()


def org_matches(expected: str, registry: str) -> str:
    if not expected:
        return "not_constrained"
    expected_low = expected.casefold()
    registry_low = registry.casefold()
    if expected_low in registry_low or registry_low in expected_low:
        return "match"
    return "mismatch_needs_title_resolution"


def find_source_dir(source_root: Path, key: str) -> Path | None:
    matches = sorted(path for path in source_root.iterdir() if path.is_dir() and path.name.startswith(key))
    if len(matches) != 1:
        return None
    return matches[0]


def build(
    candidates_path: Path,
    source_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    registry = {
        row["номер"]: row
        for row in read_csv(candidates_path, delimiter=";")
    }
    requested_numbers = sorted({row["source_number"] for row in MEMBERSHIPS})
    missing_registry = sorted(number for number in requested_numbers if number not in registry)
    if missing_registry:
        raise ValueError(f"Missing registry objects: {missing_registry}")

    object_rows: list[dict[str, Any]] = []
    for number in requested_numbers:
        row = registry[number]
        key = archive_key(number)
        source_dir = find_source_dir(source_root, key)
        files = (
            [path for path in source_dir.rglob("*") if path.is_file()]
            if source_dir
            else []
        )
        pdfs = [path for path in files if path.suffix.casefold() == ".pdf"]
        xmls = [path for path in files if path.suffix.casefold() == ".xml"]
        archives = [
            path
            for path in files
            if path.suffix.casefold() in {".zip", ".rar", ".7z"}
        ]
        memberships = [
            membership
            for membership in MEMBERSHIPS
            if membership["source_number"] == number
        ]
        expected_gips = sorted({item["expected_gip_human"] for item in memberships})
        expected_orgs = sorted(
            {item["expected_org_human"] for item in memberships if item["expected_org_human"]}
        )
        expected_work_types = sorted(
            {item["expected_work_type_human"] for item in memberships}
        )
        registry_gip = row["dev_ГИП(доп_2)"]
        registry_org = row["орг(проектировщик)"]
        registry_work_type = normalize_work_type(row["группа(вид_работ)"])
        target_pdfs = [
            path
            for path in pdfs
            if "раздел 13" not in path.name.casefold()
            and "_ид_" not in path.name.casefold()
            and not path.name.casefold().startswith("ид")
        ]
        object_rows.append(
            {
                "object_id": key,
                "source_number": number,
                "address": row["название"],
                "expected_gip_human": "|".join(expected_gips),
                "expected_org_human": "|".join(expected_orgs),
                "expected_work_type_human": "|".join(expected_work_types),
                "registry_dev_gip": registry_gip,
                "registry_org": registry_org,
                "registry_work_type": registry_work_type,
                "gip_registry_status": (
                    "match"
                    if all(gip.casefold() == registry_gip.casefold() for gip in expected_gips)
                    else "mismatch_needs_title_resolution"
                ),
                "org_registry_status": (
                    "|".join(org_matches(org, registry_org) for org in expected_orgs)
                    if expected_orgs
                    else "not_constrained"
                ),
                "work_type_registry_status": (
                    "match"
                    if all(
                        normalize_work_type(work_type) == registry_work_type
                        for work_type in expected_work_types
                    )
                    else "mismatch_needs_title_resolution"
                ),
                "source_dir": str(source_dir) if source_dir else "",
                "pdf_count": len(pdfs),
                "target_pdf_candidate_count": len(target_pdfs),
                "xml_count": len(xmls),
                "archive_count": len(archives),
                "total_file_count": len(files),
                "source_readiness": (
                    "target_pdf_candidate_ready"
                    if target_pdfs
                    else "non_target_pdf_only"
                    if pdfs
                    else "archive_only"
                    if archives
                    else "empty_or_missing"
                ),
                "title_ground_truth_status": "pending_export_and_extraction",
                "title_organization_count": "",
                "title_gip_count": "",
                "title_effective_author_gip": "",
            }
        )

    membership_rows: list[dict[str, Any]] = []
    objects_by_number = {row["source_number"]: row for row in object_rows}
    for index, membership in enumerate(MEMBERSHIPS, start=1):
        obj = objects_by_number[membership["source_number"]]
        membership_rows.append(
            {
                "membership_id": f"gipm_v0_{index:03d}",
                **membership,
                "object_id": obj["object_id"],
                "address": obj["address"],
                "registry_gip": obj["registry_dev_gip"],
                "registry_org": obj["registry_org"],
                "registry_work_type": obj["registry_work_type"],
                "source_readiness": obj["source_readiness"],
                "validity_rule": "exclude_same_project_split",
                "ground_truth_source": "title_pages_authoritative",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_priority_objects_v0.csv",
        object_rows,
        list(object_rows[0]),
    )
    write_csv(
        output_dir / "gip_priority_memberships_v0.csv",
        membership_rows,
        list(membership_rows[0]),
    )

    summary = {
        "schema_version": "gip_priority_manifest_v0",
        "generated_at": generated_at,
        "unique_object_count": len(object_rows),
        "membership_count": len(membership_rows),
        "scheme_membership_counts": dict(
            sorted(Counter(row["scheme"] for row in membership_rows).items())
        ),
        "gip_object_counts": dict(
            sorted(Counter(row["registry_dev_gip"] for row in object_rows).items())
        ),
        "registry_org_object_counts": dict(
            sorted(Counter(row["registry_org"] for row in object_rows).items())
        ),
        "source_readiness_counts": dict(
            sorted(Counter(row["source_readiness"] for row in object_rows).items())
        ),
        "registry_mismatch_objects": [
            {
                "object_id": row["object_id"],
                "gip_registry_status": row["gip_registry_status"],
                "org_registry_status": row["org_registry_status"],
                "work_type_registry_status": row["work_type_registry_status"],
            }
            for row in object_rows
            if "mismatch" in "|".join(
                [
                    row["gip_registry_status"],
                    row["org_registry_status"],
                    row["work_type_registry_status"],
                ]
            )
        ],
        "rules": [
            "human cohort design is the experiment plan.",
            "xlsx organization/GIP/work type are candidate metadata only.",
            "title pages are authoritative ground truth.",
            "all title organization-GIP pairs must be extracted.",
            "same-project OВ/GВС splits are invalid for GIP factor tests.",
        ],
        "files": {
            "objects": "gip_priority_objects_v0.csv",
            "memberships": "gip_priority_memberships_v0.csv",
        },
    }
    (output_dir / "gip_priority_manifest_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build prioritized GIP factor-test corpus manifest."
    )
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.candidates, args.source_root, args.output_dir),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
