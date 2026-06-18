#!/usr/bin/env python3
"""Build generic page-level near-match candidates and title-page evaluation.

Page similarity is calculated from domain-neutral element counts,
compositions, and group areas. Title-page labels and cohort labels are external
evaluation metadata and do not enter the similarity score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from text_features import normalize_text, sha1_text


DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view")
DEFAULT_CORPUS_DIR = Path(r"E:\output\DocSpectrum\corpus_frequency_v0_rpsk35_nk34")
DEFAULT_REGISTRY = Path(r"E:\repos\checker-shared-project\registries\title_pages_by_crc.csv")
DEFAULT_NK_INPUT = Path(
    r"E:\repos\checker-shared-project\projects\docspectrum\inputs\title_pages_nk_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\page_near_match_v0")
GROUPS = ("text", "lines", "frames", "images", "tables", "other_vector")
COUNT_COLUMNS = {
    "text": "text_count",
    "lines": "line_count",
    "frames": "frame_count",
    "images": "image_count",
    "tables": "table_count",
}


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_reference_csv(path: Path) -> list[dict[str, str]]:
    lines = [
        line
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))


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


def quantile(values: list[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


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


def parse_pages(value: str) -> set[int]:
    pages: set[int] = set()
    for part in (value or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            start = safe_int(start_raw)
            end = safe_int(end_raw)
            if start > 0 and end >= start:
                pages.update(range(start, end + 1))
        else:
            page = safe_int(part)
            if page > 0:
                pages.add(page)
    return pages


def load_title_pages(paths: list[Path]) -> dict[str, set[int]]:
    title_pages: dict[str, set[int]] = {}
    for path in paths:
        for row in read_reference_csv(path):
            crc32 = (row.get("crc32") or "").lower()
            if not crc32 or row.get("confidence") != "high":
                continue
            incoming = parse_pages(row.get("title_anchor_pages", ""))
            if crc32 in title_pages and title_pages[crc32] != incoming:
                raise ValueError(f"Conflicting title-page reference for {crc32}")
            title_pages[crc32] = incoming
    return title_pages


def parse_group_areas(source: str) -> dict[str, float]:
    areas = {group: 0.0 for group in GROUPS}
    marker = "|groups:"
    if marker not in source:
        return areas
    group_part = source.split(marker, 1)[1]
    for item in group_part.split(";"):
        parts = item.split(":")
        if len(parts) < 3:
            continue
        group = parts[0]
        if group in areas:
            areas[group] = safe_float(parts[2])
    return areas


def build_page_profile(
    row: dict[str, str],
    object_to_cohort: dict[str, str],
    title_pages: dict[str, set[int]],
) -> dict[str, Any]:
    counts = {}
    known_count = 0
    for group, column in COUNT_COLUMNS.items():
        counts[group] = safe_float(row[column])
        known_count += safe_int(row[column])
    counts["other_vector"] = max(0.0, safe_float(row["element_count"]) - known_count)
    areas = parse_group_areas(row.get("page_signature_source", ""))
    count_total = sum(counts.values())
    area_total = sum(areas.values())
    crc32 = row["crc32"].lower()
    page_number = safe_int(row["page_number"])
    return {
        "object_id": row["object_id"],
        "bundle_id": row["bundle_id"],
        "section_code": row["section_code"],
        "crc32": crc32,
        "page_id": row["page_id"],
        "page_number": page_number,
        "page_size_key": row["page_size_key"],
        "page_signature": row["page_signature"],
        "cohort": object_to_cohort.get(row["object_id"], "UNKNOWN"),
        "page_role": "title_anchor" if page_number in title_pages.get(crc32, set()) else "other",
        "element_count": safe_float(row["element_count"]),
        "counts": counts,
        "count_shares": {
            group: counts[group] / count_total if count_total else 0.0 for group in GROUPS
        },
        "areas": areas,
        "area_shares": {
            group: areas[group] / area_total if area_total else 0.0 for group in GROUPS
        },
    }


def ratio_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    values = []
    for key in left:
        a = left[key]
        b = right[key]
        if a == 0.0 and b == 0.0:
            continue
        values.append(min(a, b) / max(a, b))
    return sum(values) / len(values) if values else 1.0


def composition_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(min(left[key], right[key]) for key in left)


def set_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def near_match_score(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    count_ratio = ratio_similarity(left["counts"], right["counts"])
    count_composition = composition_similarity(left["count_shares"], right["count_shares"])
    area_ratio = ratio_similarity(left["areas"], right["areas"])
    area_composition = composition_similarity(left["area_shares"], right["area_shares"])
    element_ratio = (
        min(left["element_count"], right["element_count"])
        / max(left["element_count"], right["element_count"])
        if max(left["element_count"], right["element_count"]) > 0
        else 1.0
    )
    score = (
        0.30 * count_ratio
        + 0.20 * count_composition
        + 0.25 * area_ratio
        + 0.15 * area_composition
        + 0.10 * element_ratio
    )
    return {
        "near_match_similarity_v0": score,
        "count_ratio_similarity": count_ratio,
        "count_composition_similarity": count_composition,
        "area_ratio_similarity": area_ratio,
        "area_composition_similarity": area_composition,
        "element_count_ratio": element_ratio,
    }


def near_match_class(score: float, exact_match: bool) -> str:
    if exact_match:
        return "exact_match"
    if score >= 0.95:
        return "near_exact"
    if score >= 0.85:
        return "strong_near_match"
    if score >= 0.70:
        return "moderate_near_match"
    return "weak_match"


def build_shortlist_vectors(profiles: list[dict[str, Any]]) -> np.ndarray:
    raw_vectors = []
    for profile in profiles:
        log_counts = [math.log1p(profile["counts"][group]) for group in GROUPS]
        log_areas = [math.log1p(profile["areas"][group]) for group in GROUPS]
        raw_vectors.append(
            log_counts
            + list(profile["count_shares"].values())
            + log_areas
            + list(profile["area_shares"].values())
            + [math.log1p(profile["element_count"])]
        )
    matrix = np.asarray(raw_vectors, dtype=np.float32)
    max_values = np.maximum(matrix.max(axis=0), 1e-6)
    matrix = matrix / max_values
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-8)


def load_page_content_entities(
    base_dir: Path,
    export_root: Path,
    profiles: list[dict[str, Any]],
) -> dict[tuple[str, str, int], dict[str, set[str]]]:
    entities: dict[tuple[str, str, int], dict[str, set[str]]] = defaultdict(
        lambda: {
            "text_segment": set(),
            "table_layout": set(),
            "table_content": set(),
        }
    )
    documents = {(profile["object_id"], profile["bundle_id"]) for profile in profiles}
    for object_id, bundle_id in sorted(documents):
        path = export_root / object_id / bundle_id / "text_segments.csv"
        if not path.exists():
            continue
        for row in read_csv(path):
            normalized = normalize_text(row.get("normalized_text") or row.get("text_value") or "")
            if normalized:
                entities[(object_id, bundle_id, safe_int(row["page_number"]))]["text_segment"].add(
                    sha1_text(normalized)
                )

    for row in read_csv(base_dir / "table_signatures_v0.csv"):
        key = (row["object_id"], row["bundle_id"], safe_int(row["page_number"]))
        if row.get("layout_signature"):
            entities[key]["table_layout"].add(row["layout_signature"])
        if row.get("content_sha1"):
            entities[key]["table_content"].add(row["content_sha1"])
    return entities


def load_text_frequency(corpus_dir: Path) -> dict[str, dict[str, float]]:
    frequency: dict[str, dict[str, float]] = {}
    for row in read_csv(corpus_dir / "entity_frequency_v0.csv"):
        if row.get("entity_kind") != "text_segment":
            continue
        entity_hash = row["entity_hash"]
        frequency[entity_hash] = {
            "global_df_ratio": safe_float(row.get("global_df_ratio")),
            "global_idf": safe_float(row.get("global_idf")),
        }
    return frequency


def content_evidence(
    left: dict[str, Any],
    right: dict[str, Any],
    page_entities: dict[tuple[str, str, int], dict[str, set[str]]],
    text_frequency: dict[str, dict[str, float]],
    rare_text_max_global_df_ratio: float,
) -> dict[str, Any]:
    left_entities = page_entities[(left["object_id"], left["bundle_id"], left["page_number"])]
    right_entities = page_entities[(right["object_id"], right["bundle_id"], right["page_number"])]
    text_shared = left_entities["text_segment"] & right_entities["text_segment"]
    layout_shared = left_entities["table_layout"] & right_entities["table_layout"]
    content_shared = left_entities["table_content"] & right_entities["table_content"]
    shared_frequency = [
        text_frequency.get(entity_hash, {"global_df_ratio": 1.0, "global_idf": 0.0})
        for entity_hash in text_shared
    ]
    rare_shared = [
        meta
        for meta in shared_frequency
        if meta["global_df_ratio"] <= rare_text_max_global_df_ratio
    ]
    return {
        "text_segment_jaccard": set_jaccard(
            left_entities["text_segment"],
            right_entities["text_segment"],
        ),
        "shared_text_segment_count": len(text_shared),
        "rare_shared_text_segment_count": len(rare_shared),
        "shared_text_global_idf_sum": sum(meta["global_idf"] for meta in shared_frequency),
        "max_shared_text_global_idf": max(
            (meta["global_idf"] for meta in shared_frequency),
            default=0.0,
        ),
        "table_layout_jaccard": set_jaccard(
            left_entities["table_layout"],
            right_entities["table_layout"],
        ),
        "shared_table_layout_count": len(layout_shared),
        "table_content_jaccard": set_jaccard(
            left_entities["table_content"],
            right_entities["table_content"],
        ),
        "shared_table_content_count": len(content_shared),
    }


def evidence_class(structural_score: float, evidence: dict[str, Any]) -> str:
    if structural_score < 0.85:
        return "below_strong_structural"
    if evidence["shared_table_content_count"] > 0 and evidence["shared_text_segment_count"] > 0:
        return "structure_text_table_content"
    if evidence["shared_table_content_count"] > 0:
        return "structure_table_content"
    if evidence["rare_shared_text_segment_count"] > 0 and evidence["text_segment_jaccard"] >= 0.2:
        return "structure_rare_text_review"
    if evidence["text_segment_jaccard"] >= 0.5:
        return "structure_strong_text"
    if evidence["shared_text_segment_count"] > 0:
        return "structure_text_bridge"
    if evidence["shared_table_layout_count"] > 0:
        return "structure_table_layout"
    return "structural_only"


def review_candidate_strength(row: dict[str, Any]) -> str | None:
    if safe_float(row["near_match_similarity_v0"]) < 0.85:
        return None
    if safe_int(row["shared_table_content_count"]) > 0:
        return "table_content_overlap"
    if (
        safe_int(row["rare_shared_text_segment_count"]) > 0
        and safe_float(row["text_segment_jaccard"]) >= 0.5
    ):
        return "rare_text_high_overlap"
    if (
        safe_int(row["rare_shared_text_segment_count"]) > 0
        and safe_float(row["text_segment_jaccard"]) >= 0.2
    ):
        return "rare_text_partial_overlap"
    return None


def canonical_page_pair(row: dict[str, Any]) -> tuple[str, str]:
    left = f"{row['query_crc32']}:{row['query_page_number']}"
    right = f"{row['neighbor_crc32']}:{row['neighbor_page_number']}"
    return tuple(sorted((left, right)))


def review_candidate_id(pair_key: tuple[str, str]) -> str:
    raw = f"page_near_match_candidate_v0|{pair_key[0]}|{pair_key[1]}"
    return "pnmc_v0_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def candidate_indices(
    vectors: np.ndarray,
    profiles: list[dict[str, Any]],
    shortlist_size: int,
    block_size: int,
) -> dict[tuple[int, str], list[int]]:
    result: dict[tuple[int, str], list[int]] = {}
    cohort_array = np.asarray([profile["cohort"] for profile in profiles], dtype=object)
    doc_array = np.asarray(
        [f"{profile['object_id']}|{profile['bundle_id']}" for profile in profiles],
        dtype=object,
    )
    page_count = len(profiles)
    for start in range(0, page_count, block_size):
        end = min(start + block_size, page_count)
        scores = vectors[start:end] @ vectors.T
        for local_index, query_index in enumerate(range(start, end)):
            row_scores = scores[local_index].copy()
            row_scores[doc_array == doc_array[query_index]] = -np.inf
            for mode in ("any", "cross_org"):
                mode_scores = row_scores.copy()
                if mode == "cross_org":
                    mode_scores[cohort_array == cohort_array[query_index]] = -np.inf
                valid_count = int(np.isfinite(mode_scores).sum())
                k = min(shortlist_size, valid_count)
                if k <= 0:
                    result[(query_index, mode)] = []
                    continue
                indices = np.argpartition(mode_scores, -k)[-k:]
                indices = indices[np.argsort(-mode_scores[indices], kind="stable")]
                result[(query_index, mode)] = [int(index) for index in indices]
    return result


def build(
    base_dir: Path,
    export_root: Path,
    corpus_dir: Path,
    registry_paths: list[Path],
    output_dir: Path,
    cohorts: list[tuple[str, Path]],
    shortlist_size: int,
    top_n: int,
    block_size: int,
    rare_text_max_global_df_ratio: float,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_counts = load_object_cohorts(cohorts)
    title_pages = load_title_pages(registry_paths)
    page_rows = read_csv(base_dir / "page_signatures_v0.csv")
    profiles = [build_page_profile(row, object_to_cohort, title_pages) for row in page_rows]
    page_entities = load_page_content_entities(base_dir, export_root, profiles)
    text_frequency = load_text_frequency(corpus_dir)
    vectors = build_shortlist_vectors(profiles)
    shortlists = candidate_indices(vectors, profiles, shortlist_size, block_size)
    signature_indices: dict[str, list[int]] = defaultdict(list)
    for index, profile in enumerate(profiles):
        signature_indices[profile["page_signature"]].append(index)

    neighbor_rows: list[dict[str, Any]] = []
    for query_index, query in enumerate(profiles):
        for search_mode in ("any", "cross_org"):
            reranked = []
            candidate_pool = set(shortlists[(query_index, search_mode)])
            for candidate_index in signature_indices[query["page_signature"]]:
                candidate = profiles[candidate_index]
                if candidate_index == query_index:
                    continue
                if (
                    candidate["object_id"] == query["object_id"]
                    and candidate["bundle_id"] == query["bundle_id"]
                ):
                    continue
                if search_mode == "cross_org" and candidate["cohort"] == query["cohort"]:
                    continue
                candidate_pool.add(candidate_index)

            for candidate_index in candidate_pool:
                candidate = profiles[candidate_index]
                metrics = near_match_score(query, candidate)
                exact_match = query["page_signature"] == candidate["page_signature"]
                evidence = content_evidence(
                    query,
                    candidate,
                    page_entities,
                    text_frequency,
                    rare_text_max_global_df_ratio,
                )
                reranked.append(
                    (
                        metrics["near_match_similarity_v0"],
                        exact_match,
                        candidate["crc32"],
                        candidate["page_number"],
                        candidate,
                        metrics,
                        evidence,
                        exact_match,
                    )
                )
            reranked.sort(key=lambda item: (-item[0], -int(item[1]), item[2], item[3]))
            for rank, (_, _, _, _, candidate, metrics, evidence, exact_match) in enumerate(
                reranked[:top_n],
                start=1,
            ):
                score = metrics["near_match_similarity_v0"]
                neighbor_rows.append(
                    {
                        "search_mode": search_mode,
                        "neighbor_rank": rank,
                        "query_object_id": query["object_id"],
                        "query_bundle_id": query["bundle_id"],
                        "query_section_code": query["section_code"],
                        "query_crc32": query["crc32"],
                        "query_page_number": query["page_number"],
                        "query_page_role": query["page_role"],
                        "query_cohort": query["cohort"],
                        "neighbor_object_id": candidate["object_id"],
                        "neighbor_bundle_id": candidate["bundle_id"],
                        "neighbor_section_code": candidate["section_code"],
                        "neighbor_crc32": candidate["crc32"],
                        "neighbor_page_number": candidate["page_number"],
                        "neighbor_page_role": candidate["page_role"],
                        "neighbor_cohort": candidate["cohort"],
                        "pair_type": (
                            "within_org"
                            if query["cohort"] == candidate["cohort"]
                            else "cross_org"
                        ),
                        "section_relation": (
                            "same_section"
                            if query["section_code"] == candidate["section_code"]
                            else "different_section"
                        ),
                        "exact_page_signature_match": exact_match,
                        "near_match_class": near_match_class(score, exact_match),
                        **{key: round_float(value) for key, value in metrics.items()},
                        **{
                            key: round_float(value) if isinstance(value, float) else value
                            for key, value in evidence.items()
                        },
                        "content_evidence_class": evidence_class(score, evidence),
                    }
                )

    top_rows = [row for row in neighbor_rows if safe_int(row["neighbor_rank"]) == 1]
    title_top = [row for row in top_rows if row["query_page_role"] == "title_anchor"]
    title_summary_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in title_top:
        title_summary_values[(row["search_mode"], row["pair_type"])].append(
            safe_float(row["near_match_similarity_v0"])
        )

    title_summary_rows = []
    for (search_mode, pair_type), values in sorted(title_summary_values.items()):
        title_summary_rows.append(
            {
                "search_mode": search_mode,
                "pair_type": pair_type,
                "page_count": len(values),
                "similarity_p10": round_float(quantile(values, 0.1)),
                "similarity_median": round_float(median(values)),
                "similarity_p90": round_float(quantile(values, 0.9)),
            }
        )

    class_counts = Counter(
        (row["search_mode"], row["query_page_role"], row["near_match_class"])
        for row in top_rows
    )
    title_any_counts = Counter(
        (row["pair_type"], row["section_relation"], str(row["exact_page_signature_match"]))
        for row in title_top
        if row["search_mode"] == "any"
    )
    cross_title_unlock = [
        row
        for row in title_top
        if row["search_mode"] == "cross_org"
        and not row["exact_page_signature_match"]
        and safe_float(row["near_match_similarity_v0"]) >= 0.70
    ]
    cross_org_top = [
        row
        for row in top_rows
        if row["search_mode"] == "cross_org" and row["query_page_role"] == "other"
    ]
    content_class_counts = Counter(row["content_evidence_class"] for row in cross_org_top)
    review_candidates_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for row in neighbor_rows:
        if (
            row["search_mode"] != "cross_org"
            or safe_int(row["neighbor_rank"]) != 1
            or row["exact_page_signature_match"]
        ):
            continue
        strength = review_candidate_strength(row)
        if strength is None:
            continue
        pair_key = canonical_page_pair(row)
        candidate = {
            "candidate_id": review_candidate_id(pair_key),
            "candidate_strength": strength,
            "pair_key": "|".join(pair_key),
            "left_crc32": pair_key[0].split(":", 1)[0],
            "left_page_number": pair_key[0].split(":", 1)[1],
            "right_crc32": pair_key[1].split(":", 1)[0],
            "right_page_number": pair_key[1].split(":", 1)[1],
            "query_object_id": row["query_object_id"],
            "query_bundle_id": row["query_bundle_id"],
            "query_section_code": row["query_section_code"],
            "query_cohort": row["query_cohort"],
            "neighbor_object_id": row["neighbor_object_id"],
            "neighbor_bundle_id": row["neighbor_bundle_id"],
            "neighbor_section_code": row["neighbor_section_code"],
            "neighbor_cohort": row["neighbor_cohort"],
            "section_relation": row["section_relation"],
            "near_match_similarity_v0": row["near_match_similarity_v0"],
            "text_segment_jaccard": row["text_segment_jaccard"],
            "shared_text_segment_count": row["shared_text_segment_count"],
            "rare_shared_text_segment_count": row["rare_shared_text_segment_count"],
            "shared_text_global_idf_sum": row["shared_text_global_idf_sum"],
            "max_shared_text_global_idf": row["max_shared_text_global_idf"],
            "table_layout_jaccard": row["table_layout_jaccard"],
            "shared_table_layout_count": row["shared_table_layout_count"],
            "table_content_jaccard": row["table_content_jaccard"],
            "shared_table_content_count": row["shared_table_content_count"],
            "interpretation_note": "research_shortlist_not_proof_of_copying",
        }
        existing = review_candidates_by_pair.get(pair_key)
        if existing is None or safe_float(candidate["near_match_similarity_v0"]) > safe_float(
            existing["near_match_similarity_v0"]
        ):
            review_candidates_by_pair[pair_key] = candidate
    review_candidates = sorted(
        review_candidates_by_pair.values(),
        key=lambda row: (
            -safe_float(row["near_match_similarity_v0"]),
            -safe_int(row["rare_shared_text_segment_count"]),
            row["candidate_id"],
        ),
    )
    review_strength_counts = Counter(row["candidate_strength"] for row in review_candidates)
    review_section_counts = Counter(
        (row["query_section_code"], row["neighbor_section_code"])
        for row in review_candidates
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "page_near_match_neighbors_v0.csv",
        neighbor_rows,
        [
            "search_mode",
            "neighbor_rank",
            "query_object_id",
            "query_bundle_id",
            "query_section_code",
            "query_crc32",
            "query_page_number",
            "query_page_role",
            "query_cohort",
            "neighbor_object_id",
            "neighbor_bundle_id",
            "neighbor_section_code",
            "neighbor_crc32",
            "neighbor_page_number",
            "neighbor_page_role",
            "neighbor_cohort",
            "pair_type",
            "section_relation",
            "exact_page_signature_match",
            "near_match_class",
            "near_match_similarity_v0",
            "count_ratio_similarity",
            "count_composition_similarity",
            "area_ratio_similarity",
            "area_composition_similarity",
            "element_count_ratio",
            "text_segment_jaccard",
            "shared_text_segment_count",
            "rare_shared_text_segment_count",
            "shared_text_global_idf_sum",
            "max_shared_text_global_idf",
            "table_layout_jaccard",
            "shared_table_layout_count",
            "table_content_jaccard",
            "shared_table_content_count",
            "content_evidence_class",
        ],
    )
    write_csv(
        output_dir / "page_near_match_review_candidates_v0.csv",
        review_candidates,
        [
            "candidate_id",
            "candidate_strength",
            "pair_key",
            "left_crc32",
            "left_page_number",
            "right_crc32",
            "right_page_number",
            "query_object_id",
            "query_bundle_id",
            "query_section_code",
            "query_cohort",
            "neighbor_object_id",
            "neighbor_bundle_id",
            "neighbor_section_code",
            "neighbor_cohort",
            "section_relation",
            "near_match_similarity_v0",
            "text_segment_jaccard",
            "shared_text_segment_count",
            "rare_shared_text_segment_count",
            "shared_text_global_idf_sum",
            "max_shared_text_global_idf",
            "table_layout_jaccard",
            "shared_table_layout_count",
            "table_content_jaccard",
            "shared_table_content_count",
            "interpretation_note",
        ],
    )
    write_csv(
        output_dir / "title_page_near_match_summary_v0.csv",
        title_summary_rows,
        [
            "search_mode",
            "pair_type",
            "page_count",
            "similarity_p10",
            "similarity_median",
            "similarity_p90",
        ],
    )
    write_json(
        output_dir / "page_near_match_v0.json",
        {
            "schema_version": "page_near_match_v0",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "registry_paths": [str(path) for path in registry_paths],
            "output_dir": str(output_dir),
            "page_count": len(profiles),
            "title_page_count": sum(1 for profile in profiles if profile["page_role"] == "title_anchor"),
            "cohort_counts": cohort_counts,
            "shortlist_size": shortlist_size,
            "top_n": top_n,
            "block_size": block_size,
            "rare_text_max_global_df_ratio": rare_text_max_global_df_ratio,
            "neighbor_row_count": len(neighbor_rows),
            "top_neighbor_class_counts": {
                f"{mode}:{role}:{match_class}": count
                for (mode, role, match_class), count in sorted(class_counts.items())
            },
            "title_any_neighbor_counts": {
                f"{pair_type}:{section_relation}:exact={exact}": count
                for (pair_type, section_relation, exact), count in sorted(title_any_counts.items())
            },
            "cross_org_title_near_match_unlock_count": len(cross_title_unlock),
            "cross_org_body_content_evidence_counts": dict(sorted(content_class_counts.items())),
            "review_candidate_count": len(review_candidates),
            "review_candidate_strength_counts": dict(sorted(review_strength_counts.items())),
            "review_candidate_section_counts": {
                f"{left}|{right}": count
                for (left, right), count in sorted(review_section_counts.items())
            },
            "title_summary": title_summary_rows,
            "files": {
                "neighbors": "page_near_match_neighbors_v0.csv",
                "title_summary": "title_page_near_match_summary_v0.csv",
                "review_candidates": "page_near_match_review_candidates_v0.csv",
            },
            "modeling_rules": [
                "shortlisting uses domain-neutral page vectors without page size.",
                "final near-match score uses counts, count composition, group areas, area composition, and total element ratio.",
                "same-document pages are excluded from candidate neighbors.",
                "cohort labels affect only the cross_org evaluation/search mode, never the similarity score.",
                "title labels are external evaluation metadata joined by CRC32.",
                "exact page signature remains a baseline flag, not part of the near-match score.",
                "exact-signature candidates are injected into the shortlist so near-match cannot regress exact recall.",
                "text/table content hashes are diagnostics used to separate structural form similarity from content reuse.",
                "rare page-text review evidence uses global corpus DF/IDF and a configurable maximum global DF ratio.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build generic page near-match candidates v0.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--registry", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--shortlist-size", type=int, default=40)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--rare-text-max-global-df-ratio", type=float, default=0.25)
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat for each organization/cohort.",
    )
    args = parser.parse_args()
    registry_paths = args.registry or [DEFAULT_REGISTRY, DEFAULT_NK_INPUT]
    build(
        args.base_dir,
        args.export_root,
        args.corpus_dir,
        registry_paths,
        args.output_dir,
        args.cohort,
        args.shortlist_size,
        args.top_n,
        args.block_size,
        args.rare_text_max_global_df_ratio,
    )


if __name__ == "__main__":
    main()
