#!/usr/bin/env python3
"""Build a v0 candidate library of typical table-centric elements.

The v0 library is deliberately candidate-oriented. It starts from table layout
signatures because they provide a stable form signal while allowing content to
vary. Per-occurrence locations and cell hashes are stored in a separate evidence
table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from text_features import normalize_text, sha1_text


DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\typical_element_candidates_v0")


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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def parse_cohort(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("Cohort must use NAME=EXPORT_ROOT format.")
    name, path = raw.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("Cohort name must not be empty.")
    return name, Path(path.strip())


def load_object_cohorts(cohorts: list[tuple[str, Path]]) -> tuple[dict[str, str], dict[str, int]]:
    object_to_cohort: dict[str, str] = {}
    cohort_counts: dict[str, int] = {}
    collisions: dict[str, set[str]] = defaultdict(set)
    for cohort_name, export_root in cohorts:
        object_ids = sorted(path.name for path in export_root.iterdir() if path.is_dir())
        cohort_counts[cohort_name] = len(object_ids)
        for object_id in object_ids:
            if object_id in object_to_cohort and object_to_cohort[object_id] != cohort_name:
                collisions[object_id].update({object_to_cohort[object_id], cohort_name})
            object_to_cohort[object_id] = cohort_name
    if collisions:
        details = ", ".join(f"{key}: {sorted(value)}" for key, value in sorted(collisions.items())[:10])
        raise ValueError(f"Object ids are not unique across cohorts: {details}")
    return object_to_cohort, cohort_counts


def candidate_id(section_code: str, candidate_kind: str, signature_group: str) -> str:
    raw = f"typical_element_candidate_v0|{section_code}|{candidate_kind}|{signature_group}"
    return "tec_v0_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_table_cell_hashes_by_table(export_root: Path, object_id: str, bundle_id: str) -> dict[str, list[str]]:
    path = export_root / object_id / bundle_id / "table_cells.csv"
    if not path.exists():
        return {}
    by_table: dict[str, set[str]] = defaultdict(set)
    for row in read_csv(path):
        normalized = normalize_text(row.get("text_value") or "")
        if normalized:
            by_table[row.get("table_id", "")].add(sha1_text(normalized))
    return {table_id: sorted(hashes) for table_id, hashes in by_table.items()}


def table_cell_hashes(
    export_root: Path,
    object_id: str,
    bundle_id: str,
    table_id: str,
    cache: dict[tuple[str, str], dict[str, list[str]]],
) -> list[str]:
    doc_key = (object_id, bundle_id)
    if doc_key not in cache:
        cache[doc_key] = load_table_cell_hashes_by_table(export_root, object_id, bundle_id)
    return cache[doc_key].get(table_id, [])


def classify_content_variability(content_counts: Counter[str], object_count: int) -> str:
    if not content_counts:
        return "unknown"
    if len(content_counts) == 1:
        return "same_content"
    dominant_ratio = max(content_counts.values()) / max(1, object_count)
    if dominant_ratio >= 0.8:
        return "mostly_same_content"
    return "stable_form_variable_content"


def classify_org_distinctiveness(org_object_counts: Counter[str], section_org_counts: dict[str, int]) -> tuple[str, str, int, float, float, float]:
    if not org_object_counts:
        return "unknown", "", 0, 0.0, 0.0, 0.0
    ratios = []
    for org, count in org_object_counts.items():
        denominator = max(1, section_org_counts.get(org, 0))
        ratios.append((count / denominator, org, count))
    ratios.sort(reverse=True)
    dominant_ratio, dominant_org, dominant_count = ratios[0]
    second_ratio = ratios[1][0] if len(ratios) > 1 else 0.0
    delta = dominant_ratio - second_ratio
    if len(ratios) == 1:
        org_class = "org_specific"
    elif delta >= 0.25:
        org_class = "org_distinctive"
    else:
        org_class = "cross_org_common"
    return org_class, dominant_org, dominant_count, dominant_ratio, second_ratio, delta


def build(
    base_dir: Path,
    export_root: Path,
    output_dir: Path,
    cohorts: list[tuple[str, Path]],
    min_objects: int,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_object_counts = load_object_cohorts(cohorts)
    documents = [row for row in read_csv(base_dir / "documents_index.csv") if row.get("section_code") != "UNKNOWN"]
    tables = [row for row in read_csv(base_dir / "table_signatures_v0.csv") if row.get("layout_signature")]

    section_objects: dict[str, set[str]] = defaultdict(set)
    section_documents: dict[str, set[tuple[str, str]]] = defaultdict(set)
    section_org_objects: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in documents:
        section_code = row["section_code"]
        object_id = row["object_id"]
        cohort = object_to_cohort.get(object_id, "UNKNOWN")
        section_objects[section_code].add(object_id)
        section_documents[section_code].add((object_id, row["bundle_id"]))
        section_org_objects[section_code][cohort].add(object_id)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in tables:
        grouped[(row["section_code"], row["layout_signature"])].append(row)

    candidate_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    cell_hash_cache: dict[tuple[str, str], dict[str, list[str]]] = {}
    skipped_small = 0

    for (section_code, layout_signature), occurrences in sorted(grouped.items()):
        objects = sorted({row["object_id"] for row in occurrences})
        if len(objects) < min_objects:
            skipped_small += 1
            continue

        docs = sorted({(row["object_id"], row["bundle_id"]) for row in occurrences})
        org_object_counts = Counter()
        org_occurrence_counts = Counter()
        content_counts = Counter(row.get("content_sha1") or "" for row in occurrences if row.get("content_sha1"))
        row_counts = Counter(row.get("row_count") for row in occurrences)
        column_counts = Counter(row.get("column_count") for row in occurrences)
        cell_counts = Counter(row.get("cell_count") for row in occurrences)
        for object_id in objects:
            org_object_counts[object_to_cohort.get(object_id, "UNKNOWN")] += 1
        for row in occurrences:
            org_occurrence_counts[object_to_cohort.get(row["object_id"], "UNKNOWN")] += 1

        section_object_count = len(section_objects[section_code])
        section_document_count = len(section_documents[section_code])
        section_org_counts = {org: len(values) for org, values in section_org_objects[section_code].items()}
        org_class, dominant_org, dominant_count, dominant_ratio, second_ratio, delta = classify_org_distinctiveness(
            org_object_counts,
            section_org_counts,
        )
        cid = candidate_id(section_code, "table_layout_form", layout_signature)
        content_variability = classify_content_variability(content_counts, len(objects))
        recurrence_object_ratio = len(objects) / max(1, section_object_count)
        recurrence_document_ratio = len(docs) / max(1, section_document_count)
        section_idf = math.log((section_document_count + 1) / (len(docs) + 1)) + 1.0
        candidate_status = "candidate"
        reliability_note = "table_layout_signature_exact; near_match_pending"
        if content_variability == "stable_form_variable_content":
            reliability_note += "; stable_form_variable_content"
        elif content_variability in {"same_content", "mostly_same_content"}:
            reliability_note += "; content_reuse_check"

        candidate_rows.append(
            {
                "candidate_id": cid,
                "schema_version": "typical_element_candidate_v0",
                "candidate_class": "typical_form",
                "candidate_kind": "table_layout_form",
                "candidate_subclass": "table_form_candidate",
                "section_code": section_code,
                "primary_entity_kind": "table_layout_signature",
                "signature_group_hash": layout_signature,
                "signature_group": f"table_layout_signature:{layout_signature}",
                "row_count_mode": row_counts.most_common(1)[0][0] if row_counts else "",
                "column_count_mode": column_counts.most_common(1)[0][0] if column_counts else "",
                "cell_count_mode": cell_counts.most_common(1)[0][0] if cell_counts else "",
                "recurrence_object_count": len(objects),
                "recurrence_document_count": len(docs),
                "occurrence_count": len(occurrences),
                "section_object_count": section_object_count,
                "section_document_count": section_document_count,
                "coverage_object_ratio": round_float(recurrence_object_ratio),
                "coverage_document_ratio": round_float(recurrence_document_ratio),
                "section_idf": round_float(section_idf),
                "org_scope": "cross_org" if len(org_object_counts) > 1 else "single_org",
                "org_distinctiveness_class": org_class,
                "dominant_org": dominant_org,
                "dominant_org_object_count": dominant_count,
                "dominant_org_object_ratio": round_float(dominant_ratio),
                "second_org_object_ratio": round_float(second_ratio),
                "org_distinctiveness_delta": round_float(delta),
                "org_object_counts": "|".join(f"{org}:{count}" for org, count in sorted(org_object_counts.items())),
                "org_occurrence_counts": "|".join(f"{org}:{count}" for org, count in sorted(org_occurrence_counts.items())),
                "content_variability": content_variability,
                "content_signature_unique_count": len(content_counts),
                "dominant_content_signature_ratio": round_float(
                    max(content_counts.values()) / max(1, len(occurrences)) if content_counts else 0.0
                ),
                "near_match_status": "not_evaluated",
                "candidate_status": candidate_status,
                "reliability_note": reliability_note,
            }
        )

        for row in occurrences:
            cell_hashes = table_cell_hashes(
                export_root,
                row["object_id"],
                row["bundle_id"],
                row["table_id"],
                cell_hash_cache,
            )
            cohort = object_to_cohort.get(row["object_id"], "UNKNOWN")
            evidence_rows.append(
                {
                    "candidate_id": cid,
                    "section_code": section_code,
                    "object_id": row["object_id"],
                    "bundle_id": row["bundle_id"],
                    "cohort": cohort,
                    "org": cohort,
                    "crc32": row.get("crc32"),
                    "page_number": row.get("page_number"),
                    "table_id": row.get("table_id"),
                    "layout_signature": layout_signature,
                    "content_sha1": row.get("content_sha1"),
                    "row_count": row.get("row_count"),
                    "column_count": row.get("column_count"),
                    "cell_count": row.get("cell_count"),
                    "text_element_count": row.get("text_element_count"),
                    "line_element_count": row.get("line_element_count"),
                    "frame_element_count": row.get("frame_element_count"),
                    "bbox_area": row.get("bbox_area"),
                    "cell_text_hash_count": len(cell_hashes),
                    "cell_text_hashes": "|".join(cell_hashes[:50]),
                    "cell_text_hashes_truncated": len(cell_hashes) > 50,
                    "location_key": f"{row['object_id']}:{row['bundle_id']}:p{row.get('page_number')}:table:{row.get('table_id')}",
                }
            )

    candidate_rows.sort(
        key=lambda row: (
            row["section_code"],
            -safe_int(row["recurrence_object_count"]),
            row["org_distinctiveness_class"],
            row["candidate_id"],
        )
    )
    evidence_rows.sort(key=lambda row: (row["candidate_id"], row["object_id"], row["page_number"], row["table_id"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    write_csv(
        output_dir / "typical_element_candidates_v0.csv",
        candidate_rows,
        [
            "candidate_id",
            "schema_version",
            "candidate_class",
            "candidate_kind",
            "candidate_subclass",
            "section_code",
            "primary_entity_kind",
            "signature_group_hash",
            "signature_group",
            "row_count_mode",
            "column_count_mode",
            "cell_count_mode",
            "recurrence_object_count",
            "recurrence_document_count",
            "occurrence_count",
            "section_object_count",
            "section_document_count",
            "coverage_object_ratio",
            "coverage_document_ratio",
            "section_idf",
            "org_scope",
            "org_distinctiveness_class",
            "dominant_org",
            "dominant_org_object_count",
            "dominant_org_object_ratio",
            "second_org_object_ratio",
            "org_distinctiveness_delta",
            "org_object_counts",
            "org_occurrence_counts",
            "content_variability",
            "content_signature_unique_count",
            "dominant_content_signature_ratio",
            "near_match_status",
            "candidate_status",
            "reliability_note",
        ],
    )
    write_csv(
        output_dir / "typical_element_candidate_evidence_v0.csv",
        evidence_rows,
        [
            "candidate_id",
            "section_code",
            "object_id",
            "bundle_id",
            "cohort",
            "org",
            "crc32",
            "page_number",
            "table_id",
            "layout_signature",
            "content_sha1",
            "row_count",
            "column_count",
            "cell_count",
            "text_element_count",
            "line_element_count",
            "frame_element_count",
            "bbox_area",
            "cell_text_hash_count",
            "cell_text_hashes",
            "cell_text_hashes_truncated",
            "location_key",
        ],
    )
    class_counts = Counter(row["org_distinctiveness_class"] for row in candidate_rows)
    section_counts = Counter(row["section_code"] for row in candidate_rows)
    write_json(
        output_dir / "typical_element_candidates_v0.json",
        {
            "schema_version": "typical_element_candidates_v0",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "export_root": str(export_root),
            "output_dir": str(output_dir),
            "min_objects": min_objects,
            "cohorts": {name: str(path) for name, path in cohorts},
            "cohort_object_counts": cohort_object_counts,
            "candidate_count": len(candidate_rows),
            "evidence_row_count": len(evidence_rows),
            "table_cell_hash_cache_document_count": len(cell_hash_cache),
            "skipped_layout_groups_below_min_objects": skipped_small,
            "section_candidate_counts": dict(sorted(section_counts.items())),
            "org_distinctiveness_counts": dict(sorted(class_counts.items())),
            "files": {
                "candidates": "typical_element_candidates_v0.csv",
                "evidence": "typical_element_candidate_evidence_v0.csv",
            },
            "modeling_rules": [
                "v0 starts table-centric: one candidate is one (section_code, table_layout_signature) group.",
                "candidate_id is hash-derived from section, candidate kind and signature group.",
                "candidate rows stay thin; per-occurrence locations and cell hashes are in evidence rows.",
                "coverage is counted by distinct objects/documents, not raw occurrences, to stay size-aware.",
                "org-distinctiveness is computed after candidate extraction and does not affect core extraction.",
                "near-match is not evaluated in v0 and remains a critical follow-up.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build table-centric typical element candidates v0.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-objects", type=int, default=3)
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat for each organization/cohort.",
    )
    args = parser.parse_args()
    build(args.base_dir, args.export_root, args.output_dir, args.cohort, args.min_objects)


if __name__ == "__main__":
    main()
