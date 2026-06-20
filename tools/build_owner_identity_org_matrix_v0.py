#!/usr/bin/env python3
"""Build a library-relative organization handwriting matrix and evidence graph."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import build_gip_control_baseline_v0 as baseline
import build_gip_control_near_match_v0 as near
import build_gip_control_provenance_residual_v0 as provenance


DEFAULT_SECTIONS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0\gip_control_sections_v0.csv"
)
DEFAULT_OBJECTS = Path(
    r"E:\output\DocSpectrum\gip_control_registry_expanded_v0\gip_control_objects_v0.csv"
)
DEFAULT_EXPORT_ROOT = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_PROVENANCE = Path(
    r"E:\output\DocSpectrum\provenance_assessment_v0\page_provenance_assessment_v0.csv"
)
DEFAULT_OBJECT_XLSX = Path(r"E:\commons\DocSpectrum\Капремонт_Объекты.xlsx")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\owner_identity_org_matrix_v0")
AUTHORIAL_SECTIONS = frozenset({"АР", "КР", "ПОС", "СМ"})
AUXILIARY_NAME_RE = re.compile(r"(^|[^а-яё])(иул|уил|ул)([^а-яё]|$)", re.IGNORECASE)
STYLE_TRANSFER_THRESHOLD = 0.75
CONTENT_TRANSFER_THRESHOLD = 0.40
MIN_SUPPORTED_CELLS = 2
XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


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


def rounded(value: float | None, digits: int = 4) -> float | str:
    return "" if value is None else round(value, digits)


def median_field(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [safe_float(row.get(field)) for row in rows if row.get(field) not in ("", None)]
    return statistics.median(values) if values else None


def canonical_document(rows: list[dict[str, str]]) -> dict[str, str]:
    def rank(row: dict[str, str]) -> tuple[int, int, str]:
        auxiliary = 1 if AUXILIARY_NAME_RE.search(row.get("source_file_name", "")) else 0
        return auxiliary, -safe_int(row.get("file_size_bytes")), row.get("bundle_id", "")

    return min(rows, key=rank)


def canonical_sections(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if (
            row.get("authorship_status") == "ready"
            and row.get("section_code") in AUTHORIAL_SECTIONS
            and row.get("effective_org_canonical")
        ):
            grouped[(row["object_id"], row["section_code"])].append(row)
    return [canonical_document(members) for _, members in sorted(grouped.items())]


def calibrated_bands(provenance_path: Path) -> dict[str, dict[str, Any]]:
    rows = provenance.read_csv(provenance_path)
    metric_rows = provenance.calibrated_metric_rows(rows, provenance.DEFAULT_EXPORT_ROOTS)
    return provenance.calibrate_bands(metric_rows)


def pair_metrics(
    left_row: dict[str, str],
    right_row: dict[str, str],
    export_root: Path,
    bands: dict[str, dict[str, Any]],
    profile_cache: dict[str, dict[str, Any]],
    page_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    def profile(bundle_id: str) -> dict[str, Any]:
        if bundle_id not in profile_cache:
            profile_cache[bundle_id] = baseline.build_profile(export_root / bundle_id)
        return profile_cache[bundle_id]

    def pages(bundle_id: str) -> list[dict[str, Any]]:
        if bundle_id not in page_cache:
            page_cache[bundle_id] = near.build_document_pages(export_root / bundle_id)
        return page_cache[bundle_id]

    left_profile = profile(left_row["bundle_id"])
    right_profile = profile(right_row["bundle_id"])
    _, _, style_composition = baseline.style_score(left_profile, right_profile)
    _, content_axes = baseline.content_score(left_profile, right_profile)

    matches_lr = near.best_directional_matches(pages(left_row["bundle_id"]), pages(right_row["bundle_id"]))
    matches_rl = near.best_directional_matches(pages(right_row["bundle_id"]), pages(left_row["bundle_id"]))
    raw = near.summarize_matches(matches_lr, matches_rl)
    all_matches = matches_lr + matches_rl
    kept = []
    excluded = Counter()
    for match in all_matches:
        probe = {**match, "section_code": left_row["section_code"]}
        label, _ = provenance.classify_page_match(probe, bands)
        if label:
            excluded[label] += 1
        else:
            kept.append(probe)
    residual = provenance.summarize_residual_matches(kept)
    if residual["provenance_residual_status_v0_3"] == "measured":
        residual["provenance_residual_status_v0_3"] = (
            "measured_exclusions_applied" if excluded else "measured_no_exclusions"
        )

    return {
        "style_composition_similarity": round(style_composition, 4),
        "exact_word_shingle_jaccard": round(content_axes["text_word_shingle"], 4),
        "near_structural_similarity": raw["page_near_similarity_mean_v0_2"],
        "near_shingle_similarity": raw["page_near_shingle_mean_v0_2"],
        "near_strong_share": raw["page_near_strong_share_v0_2"],
        "residual_shingle_similarity": residual["residual_page_near_shingle_mean_v0_3"],
        "residual_strong_share": residual["residual_page_near_strong_share_v0_3"],
        "residual_status": residual["provenance_residual_status_v0_3"],
        "third_party_excluded_match_count": sum(excluded.values()),
        "third_party_excluded_labels": "|".join(
            f"{label}:{count}" for label, count in sorted(excluded.items())
        ),
    }


def parse_xlsx_table(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            "".join(node.text or "" for node in item.findall(".//x:t", XML_NS))
            for item in shared_root.findall("x:si", XML_NS)
        ]
        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    for row_node in sheet_root.findall(".//x:sheetData/x:row", XML_NS):
        row_number = safe_int(row_node.get("r"))
        values: dict[str, Any] = {}
        for cell in row_node.findall("x:c", XML_NS):
            ref = cell.get("r", "")
            column = re.match(r"[A-Z]+", ref)
            if not column:
                continue
            value_node = cell.find("x:v", XML_NS)
            if value_node is None:
                value: Any = ""
            elif cell.get("t") == "s":
                value = shared[safe_int(value_node.text)]
            else:
                value = value_node.text or ""
            values[column.group()] = value
        if row_number == 4:
            headers = {column: str(value) for column, value in values.items()}
        elif row_number >= 5 and values.get("B") not in ("", None):
            rows.append({headers.get(column, column): value for column, value in values.items()})
    return rows


def object_id_from_xlsx(row: dict[str, Any]) -> str:
    number_text = str(safe_int(row.get("номер")))
    year = safe_int(row.get("год"))
    year_suffix = f"{year % 100:02d}" if year else ""
    if len(number_text) >= 6 and year_suffix and number_text.endswith(year_suffix):
        number_text = number_text[:-2]
    number = safe_int(number_text)
    return f"{number:04d}_{year % 100:02d}" if number and year else ""


def excel_date(value: Any) -> datetime | None:
    serial = safe_float(value, -1.0)
    if serial <= 0:
        return None
    return datetime(1899, 12, 30) + timedelta(days=serial)


def temporal_by_org(
    xlsx_path: Path,
    objects: list[dict[str, str]],
) -> tuple[dict[str, Counter[str]], dict[str, str]]:
    org_by_object = {
        row["object_id"]: row.get("effective_org_canonical", "")
        for row in objects
        if row.get("effective_org_canonical")
    }
    quarter_counts: dict[str, Counter[str]] = defaultdict(Counter)
    date_by_object: dict[str, str] = {}
    for row in parse_xlsx_table(xlsx_path):
        object_id = object_id_from_xlsx(row)
        org = org_by_object.get(object_id)
        date_value = excel_date(row.get("дата_вх"))
        if not org or date_value is None:
            continue
        quarter = f"{date_value.year}-Q{(date_value.month - 1) // 3 + 1}"
        quarter_counts[org][quarter] += 1
        date_by_object[object_id] = date_value.date().isoformat()
    return quarter_counts, date_by_object


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or statistics.pstdev(left) == 0 or statistics.pstdev(right) == 0:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator if denominator else None


def temporal_relation(
    left_org: str,
    right_org: str,
    counts: dict[str, Counter[str]],
) -> dict[str, Any]:
    quarters = sorted(set(counts.get(left_org, {})) | set(counts.get(right_org, {})))
    left_counts = counts.get(left_org, {})
    right_counts = counts.get(right_org, {})
    left = [float(left_counts.get(quarter, 0)) for quarter in quarters]
    right = [float(right_counts.get(quarter, 0)) for quarter in quarters]
    correlation = pearson(left, right)
    left_total = sum(left)
    right_total = sum(right)
    best_score = 0.0
    best_direction = ""
    best_boundary = ""
    for index in range(1, len(quarters)):
        left_before = sum(left[:index]) / left_total if left_total else 0.0
        left_after = sum(left[index:]) / left_total if left_total else 0.0
        right_before = sum(right[:index]) / right_total if right_total else 0.0
        right_after = sum(right[index:]) / right_total if right_total else 0.0
        forward = left_before * right_after
        reverse = right_before * left_after
        if max(forward, reverse) > best_score:
            best_score = max(forward, reverse)
            best_direction = (
                f"{left_org} -> {right_org}" if forward >= reverse else f"{right_org} -> {left_org}"
            )
            best_boundary = quarters[index]
    return {
        "temporal_quarter_count": len(quarters),
        "temporal_activity_correlation": rounded(correlation),
        "temporal_handoff_score": rounded(best_score),
        "temporal_handoff_direction": best_direction,
        "temporal_handoff_boundary": best_boundary,
    }


def classify_link(style_retention: float | None, content_retention: float | None) -> str:
    style = style_retention is not None and style_retention >= STYLE_TRANSFER_THRESHOLD
    content = content_retention is not None and content_retention >= CONTENT_TRANSFER_THRESHOLD
    if style and content:
        return "handwriting_transfer_both"
    if style:
        return "handwriting_structure_led"
    if content:
        return "handwriting_content_led"
    return "no_transfer_at_v0_thresholds"


def connected_components(edges: list[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for left, right in edges:
        graph[left].add(right)
        graph[right].add(left)
    components = []
    seen: set[str] = set()
    for node in sorted(graph):
        if node in seen:
            continue
        stack = [node]
        component = []
        seen.add(node)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(graph[current] - seen):
                seen.add(neighbor)
                stack.append(neighbor)
        components.append(sorted(component))
    return components


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def build(
    sections_path: Path,
    objects_path: Path,
    export_root: Path,
    provenance_path: Path,
    object_xlsx: Path,
    output_dir: Path,
    max_pairs: int | None = None,
    reuse_pairs: bool = False,
) -> dict[str, Any]:
    sections = canonical_sections(read_csv(sections_path))
    objects = read_csv(objects_path)
    objects_by_id = {row["object_id"]: row for row in objects}
    bands = calibrated_bands(provenance_path)
    quarter_counts, date_by_object = temporal_by_org(object_xlsx, objects)

    cells: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in sections:
        cells[(row["work_type_key"], row["section_code"])].append(row)

    pair_path = output_dir / "owner_identity_document_pairs_v0.csv"
    if reuse_pairs and pair_path.exists():
        pair_rows = read_csv(pair_path)
    else:
        pair_rows = []
        processed = 0
        for (work_type, section_code), members in sorted(cells.items()):
            profile_cache: dict[str, dict[str, Any]] = {}
            page_cache: dict[str, list[dict[str, Any]]] = {}
            cell_pairs = [
                pair
                for pair in itertools.combinations(
                    sorted(members, key=lambda row: (row["object_id"], row["bundle_id"])), 2
                )
                if pair[0]["object_id"] != pair[1]["object_id"]
            ]
            print(f"{work_type} | {section_code}: {len(members)} docs, {len(cell_pairs)} pairs", flush=True)
            for left, right in cell_pairs:
                if max_pairs is not None and processed >= max_pairs:
                    break
                left_org = left["effective_org_canonical"]
                right_org = right["effective_org_canonical"]
                metrics = pair_metrics(left, right, export_root, bands, profile_cache, page_cache)
                pair_rows.append(
                    {
                        "cell_id": f"{work_type}|{section_code}",
                        "work_type_key": work_type,
                        "section_code": section_code,
                        "left_object_id": left["object_id"],
                        "right_object_id": right["object_id"],
                        "left_bundle_id": left["bundle_id"],
                        "right_bundle_id": right["bundle_id"],
                        "left_org": left_org,
                        "right_org": right_org,
                        "org_pair": " <> ".join(sorted((left_org, right_org))),
                        "same_org": left_org == right_org,
                        "left_gip": left.get("effective_gip", ""),
                        "right_gip": right.get("effective_gip", ""),
                        "same_gip": bool(left.get("effective_gip")) and left.get("effective_gip") == right.get("effective_gip"),
                        "left_date_in": date_by_object.get(left["object_id"], ""),
                        "right_date_in": date_by_object.get(right["object_id"], ""),
                        **metrics,
                    }
                )
                processed += 1
            if max_pairs is not None and processed >= max_pairs:
                break

    cell_org_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        org_left, org_right = sorted((row["left_org"], row["right_org"]))
        cell_org_groups[(row["cell_id"], org_left, org_right, row["section_code"])].append(row)

    cell_org_rows: list[dict[str, Any]] = []
    for (cell_id, org_left, org_right, section_code), rows in sorted(cell_org_groups.items()):
        cell_org_rows.append(
            {
                "cell_id": cell_id,
                "work_type_key": rows[0]["work_type_key"],
                "section_code": section_code,
                "org_left": org_left,
                "org_right": org_right,
                "same_org": org_left == org_right,
                "document_pair_count": len(rows),
                "style_composition_median": rounded(median_field(rows, "style_composition_similarity")),
                "residual_shingle_median": rounded(median_field(rows, "residual_shingle_similarity")),
                "residual_strong_share_median": rounded(median_field(rows, "residual_strong_share")),
            }
        )

    self_by_cell_org = {
        (row["cell_id"], row["org_left"]): row
        for row in cell_org_rows
        if row["same_org"]
    }
    for row in cell_org_rows:
        baselines = [
            self_by_cell_org.get((row["cell_id"], row["org_left"])),
            self_by_cell_org.get((row["cell_id"], row["org_right"])),
        ]
        baselines = [item for item in baselines if item]
        row["self_baseline_org_count"] = len(baselines)
        for channel in ("style_composition", "residual_shingle", "residual_strong_share"):
            current = safe_float(row.get(f"{channel}_median"), -1.0)
            reference_values = [
                safe_float(item.get(f"{channel}_median"), -1.0)
                for item in baselines
                if safe_float(item.get(f"{channel}_median"), -1.0) >= 0
            ]
            reference = statistics.fmean(reference_values) if reference_values else None
            retention = current / reference if reference not in (None, 0.0) and current >= 0 else None
            row[f"{channel}_self_reference"] = rounded(reference)
            row[f"{channel}_retention"] = rounded(retention)

    org_pair_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in cell_org_rows:
        if not row["same_org"]:
            org_pair_groups[(row["org_left"], row["org_right"])].append(row)

    gip_by_org: dict[str, set[str]] = defaultdict(set)
    title_edges = Counter()
    for row in objects:
        org = row.get("effective_org_canonical", "")
        gip = row.get("effective_gip", "")
        if org and gip:
            gip_by_org[org].add(gip)
        lead = row.get("lead_org_canonical", "")
        sub = row.get("subcontractor_org_canonical", "")
        if lead and sub and lead != sub:
            title_edges[tuple(sorted((lead, sub)))] += 1

    org_pair_rows: list[dict[str, Any]] = []
    for (org_left, org_right), rows in sorted(org_pair_groups.items()):
        supported = [row for row in rows if safe_int(row["self_baseline_org_count"]) >= 1]
        style_retention = median_field(supported, "style_composition_retention")
        content_retention = median_field(supported, "residual_shingle_retention")
        strong_retention = median_field(supported, "residual_strong_share_retention")
        style_absolute = median_field(supported, "style_composition_median")
        content_absolute = median_field(supported, "residual_shingle_median")
        strong_absolute = median_field(supported, "residual_strong_share_median")
        shared_gips = sorted(gip_by_org[org_left] & gip_by_org[org_right])
        link_class = classify_link(style_retention, content_retention)
        org_pair_rows.append(
            {
                "org_left": org_left,
                "org_right": org_right,
                "compared_cell_count": len(rows),
                "supported_cell_count": len(supported),
                "document_pair_count": sum(safe_int(row["document_pair_count"]) for row in rows),
                "sections": "|".join(sorted({row["section_code"] for row in rows})),
                "work_types": "|".join(sorted({row["work_type_key"] for row in rows})),
                "style_composition_retention_median": rounded(style_retention),
                "residual_shingle_retention_median": rounded(content_retention),
                "residual_strong_share_retention_median": rounded(strong_retention),
                "style_composition_absolute_median": rounded(style_absolute),
                "residual_shingle_absolute_median": rounded(content_absolute),
                "residual_strong_share_absolute_median": rounded(strong_absolute),
                "handwriting_link_class_v0": link_class,
                "shared_gip_count": len(shared_gips),
                "shared_gips": "|".join(shared_gips),
                "four_title_disclosed_object_count": title_edges[(org_left, org_right)],
                **temporal_relation(org_left, org_right, quarter_counts),
            }
        )

    cross_cell_rows = [
        row for row in cell_org_rows
        if not row["same_org"] and safe_int(row["self_baseline_org_count"]) >= 1
    ]
    shingle_p95 = percentile(
        [safe_float(row["residual_shingle_median"]) for row in cross_cell_rows], 0.95
    ) or 0.0
    strong_p95 = percentile(
        [safe_float(row["residual_strong_share_median"]) for row in cross_cell_rows], 0.95
    ) or 0.0
    graph_edges: list[tuple[str, str]] = []
    for row in org_pair_rows:
        support_ok = safe_int(row["supported_cell_count"]) >= MIN_SUPPORTED_CELLS
        rare_text_overlap = (
            safe_float(row["residual_shingle_absolute_median"]) >= shingle_p95
            and safe_float(row["residual_strong_share_absolute_median"]) >= strong_p95
        )
        disclosed_network = safe_int(row["four_title_disclosed_object_count"]) > 0
        handwriting_candidate = support_ok and rare_text_overlap
        graph_candidate = handwriting_candidate or disclosed_network
        row["handwriting_candidate_v0"] = handwriting_candidate
        row["disclosed_network_candidate_v0"] = disclosed_network
        row["identity_graph_candidate_v0"] = graph_candidate
        row["identity_edge_kind_v0"] = (
            "handwriting_and_disclosed_network"
            if handwriting_candidate and disclosed_network
            else "rare_handwriting_overlap"
            if handwriting_candidate
            else "disclosed_subcontract_network"
            if disclosed_network
            else ""
        )
        if graph_candidate:
            graph_edges.append((row["org_left"], row["org_right"]))

    components = connected_components(graph_edges)
    component_rows = [
        {
            "component_id": f"owner_candidate_{index:03d}",
            "organization_count": len(component),
            "organizations": "|".join(component),
            "interpretation": "library_relative_handwriting_candidate_not_owner_verdict",
        }
        for index, component in enumerate(components, 1)
    ]

    anchors = [
        ("rename_confirmed", "Комтех", "АО ССУ № 3"),
        ("owner_pair_known", "Тиволион", "ООО К1"),
        ("disclosed_subcontract_network", "Ватага", "Спектр"),
    ]
    pair_lookup = {
        (row["org_left"], row["org_right"]): row
        for row in org_pair_rows
    }
    anchor_rows = []
    for anchor_kind, left, right in anchors:
        key = tuple(sorted((left, right)))
        evidence = pair_lookup.get(key, {})
        anchor_rows.append(
            {
                "anchor_kind": anchor_kind,
                "org_left": key[0],
                "org_right": key[1],
                "matrix_pair_present": bool(evidence),
                "handwriting_link_class_v0": evidence.get("handwriting_link_class_v0", ""),
                "handwriting_candidate_v0": evidence.get("handwriting_candidate_v0", ""),
                "supported_cell_count": evidence.get("supported_cell_count", ""),
                "shared_gips": evidence.get("shared_gips", ""),
                "four_title_disclosed_object_count": evidence.get(
                    "four_title_disclosed_object_count", 0
                ),
                "temporal_handoff_score": evidence.get("temporal_handoff_score", ""),
                "temporal_handoff_direction": evidence.get("temporal_handoff_direction", ""),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "owner_identity_document_pairs_v0.csv", pair_rows, list(pair_rows[0]))
    write_csv(output_dir / "owner_identity_org_pair_cells_v0.csv", cell_org_rows, list(cell_org_rows[0]))
    write_csv(output_dir / "owner_identity_org_matrix_v0.csv", org_pair_rows, list(org_pair_rows[0]))
    write_csv(
        output_dir / "owner_identity_candidate_components_v0.csv",
        component_rows,
        list(component_rows[0]) if component_rows else ["component_id"],
    )
    write_csv(output_dir / "owner_identity_anchor_validation_v0.csv", anchor_rows, list(anchor_rows[0]))

    summary = {
        "schema_version": "owner_identity_org_matrix_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "canonical_document_count": len(sections),
        "comparison_cell_count": len(cells),
        "document_pair_count": len(pair_rows),
        "organization_pair_count": len(org_pair_rows),
        "handwriting_candidate_edge_count": len(graph_edges),
        "candidate_component_count": len(component_rows),
        "thresholds": {
            "minimum_supported_cells": MIN_SUPPORTED_CELLS,
            "style_transfer_retention": STYLE_TRANSFER_THRESHOLD,
            "content_transfer_retention": CONTENT_TRANSFER_THRESHOLD,
            "cross_org_cell_residual_shingle_p95": round(shingle_p95, 4),
            "cross_org_cell_residual_strong_share_p95": round(strong_p95, 4),
        },
        "interpretation_rules": [
            "Similarity is computed before organization/GIP/temporal/title evidence is joined.",
            "Only same work-type and section documents are compared.",
            "Org-pair cell retention is relative to available within-org baselines.",
            "Graph components are library-relative research candidates, not owner verdicts.",
            "IUL personnel data is not used as an input feature.",
        ],
    }
    write_json(output_dir / "owner_identity_org_matrix_v0.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--object-xlsx", type=Path, default=DEFAULT_OBJECT_XLSX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--reuse-pairs", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.sections,
                args.objects,
                args.export_root,
                args.provenance,
                args.object_xlsx,
                args.output_dir,
                args.max_pairs,
                args.reuse_pairs,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
