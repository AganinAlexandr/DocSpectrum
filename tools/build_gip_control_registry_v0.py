#!/usr/bin/env python3
"""Build a wide GIP-control registry over the non-UUiR broad corpus.

This layer consolidates:

- object-level title-derived authorship (`effective_author`)
- organization alias canon
- the 210-object non-UUiR titled manifest
- the 1513-section all-sections selection

It produces a reproducible registry for the first wide GIP-control experiment,
including the comparison cells needed for:

- H1: within-org, within-work-type, same-section, same-GIP vs diff-GIP
- H2: same-GIP, same-work-type, same-section, cross-org vs baseline
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_org_alias_registry_v0 import identity_hint
from text_features import normalize_text


DEFAULT_MANIFEST = Path(r"E:\output\DocSpectrum\non_uuir_titled_objects_v0.csv")
DEFAULT_SELECTION = Path(
    r"E:\output\DocSpectrum\non_uuir_all_sections_selection_v0\all_sections_run_selection_v0.csv"
)
DEFAULT_ALIAS_REGISTRY = Path(r"E:\output\DocSpectrum\org_alias_registry_v0\org_alias_registry_v0.csv")
DEFAULT_RESULTS_ROOT = Path(r"E:\output\DocSpectrum")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_control_registry_v0")


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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def clean_text_key(value: str) -> str:
    normalized = normalize_text((value or "").strip().lower())
    return " ".join(re.findall(r"[0-9a-zа-я]+", normalized))


def normalize_work_type(value: str) -> str:
    cleaned = (value or "").replace("_", " ").replace("\\", " ").replace("/", " ")
    return clean_text_key(cleaned)


def load_alias_registry(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for row in read_csv(path):
        canonical = row.get("canonical_display_hint", "").strip()
        if not canonical:
            continue
        for value in (row.get("organization_identity_hint", ""), canonical):
            key = clean_text_key(value)
            if key:
                aliases[key] = canonical
    return aliases


def organization_identity_keys(value: str) -> tuple[str, ...]:
    direct = clean_text_key(value)
    identity, _display, _legal_form = identity_hint(value, value)
    normalized_identity = clean_text_key(identity)
    return tuple(dict.fromkeys(key for key in (direct, normalized_identity) if key))


def resolve_organization_name(
    party: dict[str, str],
    alias_by_identity: dict[str, str],
) -> tuple[str, str]:
    candidates = [
        party.get("organization_name_normalized", ""),
        party.get("organization_name_raw", ""),
        party.get("organization_evidence_text", ""),
    ]
    for candidate in candidates:
        for key in organization_identity_keys(candidate):
            if key in alias_by_identity:
                return alias_by_identity[key], "alias_registry"
    for candidate in candidates:
        value = candidate.strip()
        if value:
            return value, "title_raw_fallback"
    return "", "missing"


def load_title_results(
    results_root: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    documents_by_object: dict[str, dict[str, str]] = {}
    parties_by_object: dict[str, list[dict[str, str]]] = defaultdict(list)
    for results_dir in sorted(results_root.glob("title_authorship_range_*_results_v0")):
        documents_path = results_dir / "title_authorship_documents_v0.csv"
        parties_path = results_dir / "title_authorship_parties_v0.csv"
        if not documents_path.exists() or not parties_path.exists():
            continue
        for row in read_csv(documents_path):
            object_id = row["object_id"]
            if object_id in documents_by_object:
                raise ValueError(f"Duplicate title-authorship document row for {object_id}")
            documents_by_object[object_id] = row
        for row in read_csv(parties_path):
            parties_by_object[row["object_id"]].append(row)
    return documents_by_object, parties_by_object


def select_effective_party(parties: list[dict[str, str]]) -> dict[str, str] | None:
    effective = [row for row in parties if row.get("effective_author", "").lower() == "true"]
    if effective:
        return effective[0]
    subcontractors = [row for row in parties if row.get("role") == "subcontractor"]
    if subcontractors:
        return subcontractors[0]
    leads = [row for row in parties if row.get("role") == "lead_designer"]
    if leads:
        return leads[0]
    return None


def summarize_object_row(
    manifest_row: dict[str, str],
    document_row: dict[str, str] | None,
    party_rows: list[dict[str, str]],
    alias_by_identity: dict[str, str],
) -> dict[str, Any]:
    lead_parties = [row for row in party_rows if row.get("role") == "lead_designer"]
    subcontractor_parties = [row for row in party_rows if row.get("role") == "subcontractor"]
    effective_party = select_effective_party(party_rows)

    lead_org, lead_org_source = (
        resolve_organization_name(lead_parties[0], alias_by_identity)
        if lead_parties
        else ("", "missing")
    )
    subcontractor_org, subcontractor_org_source = (
        resolve_organization_name(subcontractor_parties[0], alias_by_identity)
        if subcontractor_parties
        else ("", "missing")
    )
    effective_org, effective_org_source = (
        resolve_organization_name(effective_party, alias_by_identity)
        if effective_party
        else ("", "missing")
    )

    title_page_count = safe_int(document_row.get("title_page_count") if document_row else "")
    if effective_party is None:
        authorship_status = "missing_effective_author"
    elif not effective_party.get("gip_surname_normalized", "").strip():
        authorship_status = "missing_effective_gip"
    elif not effective_org:
        authorship_status = "missing_effective_org"
    else:
        authorship_status = "ready"

    return {
        "object_id": manifest_row["object_id"],
        "work_type_raw": manifest_row.get("group", ""),
        "work_type_key": normalize_work_type(manifest_row.get("group", "")),
        "manifest_gip_hint": clean_text_key(manifest_row.get("gip", "")),
        "manifest_org_hint": manifest_row.get("org", "").strip(),
        "title_document_section_code": document_row.get("section_code", "") if document_row else "",
        "title_document_crc32": document_row.get("crc32", "") if document_row else "",
        "title_document_id": document_row.get("expected_document_id", "") if document_row else "",
        "title_page_count": title_page_count,
        "title_structure_status": document_row.get("title_structure_status", "") if document_row else "",
        "party_group_count": safe_int(document_row.get("party_group_count") if document_row else ""),
        "lead_party_count": len(lead_parties),
        "subcontractor_party_count": len(subcontractor_parties),
        "manual_review_required": any(
            row.get("manual_review_required", "").lower() == "true" for row in party_rows
        ),
        "effective_author_rule": effective_party.get("effective_author_rule", "") if effective_party else "",
        "effective_gip": clean_text_key(effective_party.get("gip_surname_normalized", "") if effective_party else ""),
        "effective_org_canonical": effective_org,
        "effective_org_source": effective_org_source,
        "lead_gip": clean_text_key(lead_parties[0].get("gip_surname_normalized", "") if lead_parties else ""),
        "lead_org_canonical": lead_org,
        "lead_org_source": lead_org_source,
        "subcontractor_gip": clean_text_key(
            subcontractor_parties[0].get("gip_surname_normalized", "") if subcontractor_parties else ""
        ),
        "subcontractor_org_canonical": subcontractor_org,
        "subcontractor_org_source": subcontractor_org_source,
        "authorship_status": authorship_status,
    }


def object_row_to_section_row(
    selection_row: dict[str, str],
    object_row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "object_id": selection_row["object_id"],
        "section_code": selection_row["section_code"],
        "crc32": selection_row["crc32"],
        "bundle_id": selection_row["expected_document_id"],
        "analysis_target_pdf": selection_row["analysis_target_pdf"],
        "source_file_name": selection_row["source_file_name"],
        "file_size_bytes": selection_row["file_size_bytes"],
        "version_count": selection_row["version_count"],
        "export_exists_at_build": selection_row["export_exists_at_build"],
        "work_type_key": object_row["work_type_key"],
        "work_type_raw": object_row["work_type_raw"],
        "effective_gip": object_row["effective_gip"],
        "effective_org_canonical": object_row["effective_org_canonical"],
        "effective_author_rule": object_row["effective_author_rule"],
        "subcontractor_party_count": object_row["subcontractor_party_count"],
        "title_page_count": object_row["title_page_count"],
        "title_structure_status": object_row["title_structure_status"],
        "authorship_status": object_row["authorship_status"],
    }


def build_h1_cells(section_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in section_rows:
        if not row["effective_org_canonical"] or not row["effective_gip"]:
            continue
        grouped[(row["effective_org_canonical"], row["work_type_key"], row["section_code"])].append(row)

    rows: list[dict[str, Any]] = []
    for (org, work_type, section_code), members in sorted(grouped.items()):
        by_gip: dict[str, set[str]] = defaultdict(set)
        for row in members:
            by_gip[row["effective_gip"]].add(row["object_id"])
        gip_object_counts = {gip: len(object_ids) for gip, object_ids in sorted(by_gip.items())}
        object_ids = sorted({row["object_id"] for row in members})
        eligible = len(by_gip) >= 2 and len(object_ids) >= 3
        rows.append(
            {
                "cell_kind": "h1_within_org_diff_gip",
                "org_canonical": org,
                "work_type_key": work_type,
                "section_code": section_code,
                "object_count": len(object_ids),
                "gip_count": len(by_gip),
                "eligible_for_gip_control": eligible,
                "gip_object_counts": "|".join(f"{gip}:{count}" for gip, count in gip_object_counts.items()),
                "object_ids": "|".join(object_ids[:100]),
                "object_ids_truncated": len(object_ids) > 100,
            }
        )
    return rows


def build_h2_cells(section_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in section_rows:
        if not row["effective_org_canonical"] or not row["effective_gip"]:
            continue
        grouped[(row["effective_gip"], row["work_type_key"], row["section_code"])].append(row)

    rows: list[dict[str, Any]] = []
    for (gip, work_type, section_code), members in sorted(grouped.items()):
        by_org: dict[str, set[str]] = defaultdict(set)
        for row in members:
            by_org[row["effective_org_canonical"]].add(row["object_id"])
        org_object_counts = {org: len(object_ids) for org, object_ids in sorted(by_org.items())}
        object_ids = sorted({row["object_id"] for row in members})
        eligible = len(by_org) >= 2 and len(object_ids) >= 2
        rows.append(
            {
                "cell_kind": "h2_cross_org_same_gip",
                "gip": gip,
                "work_type_key": work_type,
                "section_code": section_code,
                "object_count": len(object_ids),
                "org_count": len(by_org),
                "eligible_for_gip_control": eligible,
                "org_object_counts": "|".join(f"{org}:{count}" for org, count in org_object_counts.items()),
                "object_ids": "|".join(object_ids[:100]),
                "object_ids_truncated": len(object_ids) > 100,
            }
        )
    return rows


def build(
    manifest_path: Path,
    selection_path: Path,
    alias_registry_path: Path,
    results_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest_rows = read_csv(manifest_path)
    selection_rows = read_csv(selection_path)
    alias_by_identity = load_alias_registry(alias_registry_path)
    documents_by_object, parties_by_object = load_title_results(results_root)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    object_rows = [
        summarize_object_row(
            manifest_row,
            documents_by_object.get(manifest_row["object_id"]),
            parties_by_object.get(manifest_row["object_id"], []),
            alias_by_identity,
        )
        for manifest_row in sorted(manifest_rows, key=lambda row: row["object_id"])
    ]
    object_by_id = {row["object_id"]: row for row in object_rows}

    section_rows = [
        object_row_to_section_row(selection_row, object_by_id[selection_row["object_id"]])
        for selection_row in selection_rows
        if selection_row["object_id"] in object_by_id
    ]
    h1_rows = build_h1_cells(section_rows)
    h2_rows = build_h2_cells(section_rows)
    cell_rows = h1_rows + h2_rows

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_control_objects_v0.csv",
        object_rows,
        [
            "object_id",
            "work_type_raw",
            "work_type_key",
            "manifest_gip_hint",
            "manifest_org_hint",
            "title_document_section_code",
            "title_document_crc32",
            "title_document_id",
            "title_page_count",
            "title_structure_status",
            "party_group_count",
            "lead_party_count",
            "subcontractor_party_count",
            "manual_review_required",
            "effective_author_rule",
            "effective_gip",
            "effective_org_canonical",
            "effective_org_source",
            "lead_gip",
            "lead_org_canonical",
            "lead_org_source",
            "subcontractor_gip",
            "subcontractor_org_canonical",
            "subcontractor_org_source",
            "authorship_status",
        ],
    )
    write_csv(
        output_dir / "gip_control_sections_v0.csv",
        section_rows,
        [
            "object_id",
            "section_code",
            "crc32",
            "bundle_id",
            "analysis_target_pdf",
            "source_file_name",
            "file_size_bytes",
            "version_count",
            "export_exists_at_build",
            "work_type_key",
            "work_type_raw",
            "effective_gip",
            "effective_org_canonical",
            "effective_author_rule",
            "subcontractor_party_count",
            "title_page_count",
            "title_structure_status",
            "authorship_status",
        ],
    )
    write_csv(
        output_dir / "gip_control_cells_v0.csv",
        cell_rows,
        [
            "cell_kind",
            "org_canonical",
            "gip",
            "work_type_key",
            "section_code",
            "object_count",
            "gip_count",
            "org_count",
            "eligible_for_gip_control",
            "gip_object_counts",
            "org_object_counts",
            "object_ids",
            "object_ids_truncated",
        ],
    )

    authorship_status_counts = Counter(row["authorship_status"] for row in object_rows)
    title_page_count_counts = Counter(str(row["title_page_count"]) for row in object_rows)
    effective_rule_counts = Counter(row["effective_author_rule"] for row in object_rows)
    subcontractor_count = sum(1 for row in object_rows if row["subcontractor_party_count"] > 0)
    h1_eligible = sum(1 for row in h1_rows if row["eligible_for_gip_control"])
    h2_eligible = sum(1 for row in h2_rows if row["eligible_for_gip_control"])

    summary = {
        "schema_version": "gip_control_registry_v0",
        "generated_at": generated_at,
        "manifest_path": str(manifest_path),
        "selection_path": str(selection_path),
        "alias_registry_path": str(alias_registry_path),
        "results_root": str(results_root),
        "object_count": len(object_rows),
        "section_count": len(section_rows),
        "authorship_status_counts": dict(sorted(authorship_status_counts.items())),
        "title_page_count_counts": dict(sorted(title_page_count_counts.items())),
        "effective_author_rule_counts": dict(sorted(effective_rule_counts.items())),
        "subcontractor_object_count": subcontractor_count,
        "h1_cell_count": len(h1_rows),
        "h1_eligible_cell_count": h1_eligible,
        "h2_cell_count": len(h2_rows),
        "h2_eligible_cell_count": h2_eligible,
        "files": {
            "objects": "gip_control_objects_v0.csv",
            "sections": "gip_control_sections_v0.csv",
            "cells": "gip_control_cells_v0.csv",
        },
    }
    write_json(output_dir / "gip_control_registry_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the wide GIP-control registry v0.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--alias-registry", type=Path, default=DEFAULT_ALIAS_REGISTRY)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.manifest,
                args.selection,
                args.alias_registry,
                args.results_root,
                args.output_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
