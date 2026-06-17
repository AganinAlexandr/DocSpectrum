#!/usr/bin/env python3
"""Build text typical-element candidates and section coverage v0.

This is a hash-only text layer for the consumer-facing library. It promotes
recurrent text segments and word shingles to candidate rows, keeps occurrence
evidence separate, and reports per-section-document coverage/residual.
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

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_EXPORT_ROOT = Path(r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\text_element_library_v0")
TEXT_ENTITY_KINDS = ("text_segment", "text_word_shingle")


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


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


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


def candidate_id(section_code: str, entity_kind: str, entity_hash: str) -> str:
    raw = f"text_element_candidate_v0|{section_code}|{entity_kind}|{entity_hash}"
    return "txtc_v0_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


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


def derive_candidate_class(
    org_scope: str,
    org_distinctiveness_class: str,
    section_df_ratio: float,
    copy_review_max_section_df_ratio: float,
) -> str:
    if org_scope != "cross_org":
        return "org_text_pattern"
    if org_distinctiveness_class == "cross_org_common":
        return "normative_text"
    if section_df_ratio > copy_review_max_section_df_ratio:
        return "normative_text"
    return "cross_org_text_bridge"


def derive_uc3_signal_status(candidate_class: str) -> str:
    if candidate_class == "cross_org_text_bridge":
        return "copy_review_needed"
    if candidate_class == "normative_text":
        return "normative_or_boilerplate"
    return "org_pattern"


def classify_triviality(entity_kind: str, token_count_mode: int, char_count_mode: int, min_tokens: int, min_chars: int) -> tuple[str, str]:
    if entity_kind == "text_word_shingle":
        return "meaningful_text", ""
    reasons = []
    if token_count_mode < min_tokens:
        reasons.append(f"token_count<{min_tokens}")
    if char_count_mode < min_chars:
        reasons.append(f"char_count<{min_chars}")
    if reasons:
        return "trivial_text", "|".join(reasons)
    return "meaningful_text", ""


def extract_text_occurrences(export_root: Path, doc: dict[str, str], shingle_size: int) -> list[dict[str, Any]]:
    path = export_root / doc["object_id"] / doc["bundle_id"] / "text_segments.csv"
    if not path.exists():
        return []

    occurrences: list[dict[str, Any]] = []
    for row in read_csv(path):
        normalized = normalize_text(row.get("normalized_text") or row.get("text_value") or "")
        if not normalized:
            continue
        tokens = text_tokens(normalized)
        segment_hash = sha1_text(normalized)
        base = {
            "object_id": doc["object_id"],
            "bundle_id": doc["bundle_id"],
            "section_code": doc["section_code"],
            "crc32": doc.get("crc32", ""),
            "page_number": row.get("page_number", ""),
            "text_segment_id": row.get("text_segment_id", ""),
            "encoding_status": row.get("encoding_status", ""),
            "token_count": len(tokens),
            "char_count": len(normalized),
            "x1": row.get("x1", ""),
            "y1": row.get("y1", ""),
            "x2": row.get("x2", ""),
            "y2": row.get("y2", ""),
        }
        occurrences.append(
            {
                **base,
                "entity_kind": "text_segment",
                "entity_hash": segment_hash,
                "source_text_segment_id": row.get("text_segment_id", ""),
                "shingle_index": "",
            }
        )
        for index, shingle in enumerate(word_shingles(tokens, size=shingle_size)):
            occurrences.append(
                {
                    **base,
                    "entity_kind": "text_word_shingle",
                    "entity_hash": sha1_text(shingle),
                    "source_text_segment_id": row.get("text_segment_id", ""),
                    "shingle_index": index,
                    "token_count": shingle_size,
                    "char_count": len(shingle),
                }
            )
    return occurrences


def sample_evidence_occurrences(
    occurrences: list[dict[str, Any]],
    object_to_cohort: dict[str, str],
    max_evidence_per_candidate: int,
) -> list[dict[str, Any]]:
    if len(occurrences) <= max_evidence_per_candidate:
        return occurrences

    by_cohort: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in occurrences:
        by_cohort[object_to_cohort.get(row["object_id"], "UNKNOWN")].append(row)

    sample: list[dict[str, Any]] = []
    seen_locations: set[tuple[str, str, str, str]] = set()
    per_cohort_seed = max(1, max_evidence_per_candidate // max(1, len(by_cohort)) // 2)
    for cohort in sorted(by_cohort):
        for row in by_cohort[cohort][:per_cohort_seed]:
            key = (row["object_id"], row["bundle_id"], str(row["text_segment_id"]), str(row["shingle_index"]))
            if key not in seen_locations:
                sample.append(row)
                seen_locations.add(key)

    for row in occurrences:
        if len(sample) >= max_evidence_per_candidate:
            break
        key = (row["object_id"], row["bundle_id"], str(row["text_segment_id"]), str(row["shingle_index"]))
        if key not in seen_locations:
            sample.append(row)
            seen_locations.add(key)
    return sample


def candidate_matches_expected_org(candidate: dict[str, Any], document_cohort: str) -> bool:
    if document_cohort in {"", "UNKNOWN"}:
        return False
    if candidate.get("org_distinctiveness_class") == "cross_org_common":
        return True
    return candidate.get("dominant_org") == document_cohort


def candidate_matches_foreign_org(candidate: dict[str, Any], document_cohort: str) -> bool:
    if document_cohort in {"", "UNKNOWN"}:
        return False
    if candidate.get("org_distinctiveness_class") == "cross_org_common":
        return False
    dominant_org = candidate.get("dominant_org")
    return bool(dominant_org and dominant_org != document_cohort)


def build(
    base_dir: Path,
    export_root: Path,
    output_dir: Path,
    cohorts: list[tuple[str, Path]],
    min_objects: int,
    min_segment_tokens: int,
    min_segment_chars: int,
    shingle_size: int,
    max_evidence_per_candidate: int,
    copy_review_max_section_df_ratio: float,
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_object_counts = load_object_cohorts(cohorts)
    documents = [row for row in read_csv(base_dir / "documents_index.csv") if row.get("section_code") != "UNKNOWN"]

    section_objects: dict[str, set[str]] = defaultdict(set)
    section_documents: dict[str, set[tuple[str, str]]] = defaultdict(set)
    section_org_objects: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for doc in documents:
        section_code = doc["section_code"]
        object_id = doc["object_id"]
        cohort = object_to_cohort.get(object_id, "UNKNOWN")
        section_objects[section_code].add(object_id)
        section_documents[section_code].add((object_id, doc["bundle_id"]))
        section_org_objects[section_code][cohort].add(object_id)

    all_occurrences: list[dict[str, Any]] = []
    occurrences_by_doc: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc in documents:
        doc_occurrences = extract_text_occurrences(export_root, doc, shingle_size)
        occurrences_by_doc[(doc["object_id"], doc["bundle_id"])] = doc_occurrences
        all_occurrences.extend(doc_occurrences)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for occurrence in all_occurrences:
        grouped[(occurrence["section_code"], occurrence["entity_kind"], occurrence["entity_hash"])].append(occurrence)

    candidate_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    candidates_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped_small = 0

    for (section_code, entity_kind, entity_hash), occurrences in sorted(grouped.items()):
        objects = sorted({row["object_id"] for row in occurrences})
        if len(objects) < min_objects:
            skipped_small += 1
            continue

        docs = sorted({(row["object_id"], row["bundle_id"]) for row in occurrences})
        org_object_counts = Counter(object_to_cohort.get(object_id, "UNKNOWN") for object_id in objects)
        org_occurrence_counts = Counter(object_to_cohort.get(row["object_id"], "UNKNOWN") for row in occurrences)
        token_counts = Counter(row["token_count"] for row in occurrences)
        char_counts = Counter(row["char_count"] for row in occurrences)
        section_object_count = len(section_objects[section_code])
        section_document_count = len(section_documents[section_code])
        section_org_counts = {org: len(values) for org, values in section_org_objects[section_code].items()}
        org_class, dominant_org, dominant_count, dominant_ratio, second_ratio, delta = classify_org_distinctiveness(
            org_object_counts,
            section_org_counts,
        )
        org_scope = "cross_org" if len(org_object_counts) > 1 else "single_org"
        section_df_ratio = ratio(len(docs), section_document_count)
        text_candidate_class = derive_candidate_class(
            org_scope,
            org_class,
            section_df_ratio,
            copy_review_max_section_df_ratio,
        )
        uc3_signal_status = derive_uc3_signal_status(text_candidate_class)
        token_count_mode = token_counts.most_common(1)[0][0] if token_counts else 0
        char_count_mode = char_counts.most_common(1)[0][0] if char_counts else 0
        triviality_status, triviality_reason = classify_triviality(
            entity_kind,
            token_count_mode,
            char_count_mode,
            min_segment_tokens,
            min_segment_chars,
        )
        candidate_status = "diagnostic_trivial" if triviality_status == "trivial_text" else "candidate"
        section_idf = math.log((section_document_count + 1) / (len(docs) + 1)) + 1.0
        cid = candidate_id(section_code, entity_kind, entity_hash)
        reliability_note = "exact_text_hash; near_match_pending; semantic_embeddings_not_used"
        if candidate_status == "diagnostic_trivial":
            reliability_note += "; trivial_text"
        if uc3_signal_status == "copy_review_needed":
            reliability_note += "; cross_org_exact_text_bridge_review_needed"

        candidate = {
            "candidate_id": cid,
            "schema_version": "text_element_candidate_v0",
            "candidate_class": text_candidate_class,
            "candidate_kind": entity_kind,
            "candidate_subclass": "text_hash_candidate",
            "section_code": section_code,
            "primary_entity_kind": entity_kind,
            "entity_hash": entity_hash,
            "recurrence_object_count": len(objects),
            "recurrence_document_count": len(docs),
            "occurrence_count": len(occurrences),
            "section_object_count": section_object_count,
            "section_document_count": section_document_count,
            "coverage_object_ratio": round_float(ratio(len(objects), section_object_count)),
            "coverage_document_ratio": round_float(section_df_ratio),
            "section_idf": round_float(section_idf),
            "org_scope": org_scope,
            "org_distinctiveness_class": org_class,
            "dominant_org": dominant_org,
            "dominant_org_object_count": dominant_count,
            "dominant_org_object_ratio": round_float(dominant_ratio),
            "second_org_object_ratio": round_float(second_ratio),
            "org_distinctiveness_delta": round_float(delta),
            "org_object_counts": "|".join(f"{org}:{count}" for org, count in sorted(org_object_counts.items())),
            "org_occurrence_counts": "|".join(f"{org}:{count}" for org, count in sorted(org_occurrence_counts.items())),
            "uc3_signal_status": uc3_signal_status,
            "copy_review_max_section_df_ratio": copy_review_max_section_df_ratio,
            "token_count_mode": token_count_mode,
            "char_count_mode": char_count_mode,
            "triviality_status": triviality_status,
            "triviality_reason": triviality_reason,
            "near_match_status": "not_evaluated",
            "candidate_status": candidate_status,
            "reliability_note": reliability_note,
            "evidence_occurrence_rows_emitted": min(len(occurrences), max_evidence_per_candidate),
            "evidence_truncated": len(occurrences) > max_evidence_per_candidate,
        }
        candidate_rows.append(candidate)
        candidates_by_key[(section_code, entity_kind, entity_hash)] = candidate

        evidence_sample = sample_evidence_occurrences(occurrences, object_to_cohort, max_evidence_per_candidate)
        for row in evidence_sample:
            evidence_rows.append(
                {
                    "candidate_id": cid,
                    "section_code": section_code,
                    "object_id": row["object_id"],
                    "bundle_id": row["bundle_id"],
                    "cohort": object_to_cohort.get(row["object_id"], "UNKNOWN"),
                    "crc32": row["crc32"],
                    "entity_kind": entity_kind,
                    "entity_hash": entity_hash,
                    "page_number": row["page_number"],
                    "text_segment_id": row["text_segment_id"],
                    "source_text_segment_id": row["source_text_segment_id"],
                    "shingle_index": row["shingle_index"],
                    "token_count": row["token_count"],
                    "char_count": row["char_count"],
                    "encoding_status": row["encoding_status"],
                    "x1": row["x1"],
                    "y1": row["y1"],
                    "x2": row["x2"],
                    "y2": row["y2"],
                    "location_key": (
                        f"{row['object_id']}:{row['bundle_id']}:p{row['page_number']}:"
                        f"text:{row['text_segment_id']}:{entity_kind}:{row['shingle_index']}"
                    ),
                }
            )

    coverage_rows: list[dict[str, Any]] = []
    included_statuses = {"candidate"}
    for doc in sorted(documents, key=lambda row: (row["section_code"], row["object_id"], row["bundle_id"])):
        doc_key = (doc["object_id"], doc["bundle_id"])
        document_cohort = object_to_cohort.get(doc["object_id"], "UNKNOWN")
        doc_occurrences = occurrences_by_doc.get(doc_key, [])
        totals = Counter(row["entity_kind"] for row in doc_occurrences)
        matched = Counter()
        expected = Counter()
        foreign = Counter()
        borrowing = Counter()
        class_counts = Counter()
        status_counts = Counter()
        candidate_ids: Counter[str] = Counter()

        for occurrence in doc_occurrences:
            key = (occurrence["section_code"], occurrence["entity_kind"], occurrence["entity_hash"])
            candidate = candidates_by_key.get(key)
            if not candidate or candidate.get("candidate_status") not in included_statuses:
                continue
            entity_kind = occurrence["entity_kind"]
            matched[entity_kind] += 1
            candidate_ids[candidate["candidate_id"]] += 1
            class_counts[(entity_kind, candidate["candidate_class"])] += 1
            status_counts[(entity_kind, candidate["candidate_status"])] += 1
            if candidate.get("uc3_signal_status") == "copy_review_needed":
                borrowing[entity_kind] += 1
            if candidate_matches_expected_org(candidate, document_cohort):
                expected[entity_kind] += 1
            elif candidate_matches_foreign_org(candidate, document_cohort):
                foreign[entity_kind] += 1

        segment_total = totals["text_segment"]
        shingle_total = totals["text_word_shingle"]
        segment_matched = matched["text_segment"]
        shingle_matched = matched["text_word_shingle"]
        all_total = segment_total + shingle_total
        all_matched = segment_matched + shingle_matched
        top_candidate_ids = sorted(candidate_ids.items(), key=lambda item: (-item[1], item[0]))[:50]
        coverage_rows.append(
            {
                "object_id": doc["object_id"],
                "bundle_id": doc["bundle_id"],
                "section_code": doc["section_code"],
                "cohort": document_cohort,
                "crc32": doc.get("crc32"),
                "text_segment_occurrence_count": segment_total,
                "text_segment_matched_occurrence_count": segment_matched,
                "text_segment_coverage_ratio": round_float(ratio(segment_matched, segment_total)),
                "text_segment_residual_count": segment_total - segment_matched,
                "text_segment_residual_ratio": round_float(ratio(segment_total - segment_matched, segment_total)),
                "text_shingle_occurrence_count": shingle_total,
                "text_shingle_matched_occurrence_count": shingle_matched,
                "text_shingle_coverage_ratio": round_float(ratio(shingle_matched, shingle_total)),
                "text_shingle_residual_count": shingle_total - shingle_matched,
                "text_shingle_residual_ratio": round_float(ratio(shingle_total - shingle_matched, shingle_total)),
                "text_all_occurrence_count": all_total,
                "text_all_matched_occurrence_count": all_matched,
                "text_all_coverage_ratio": round_float(ratio(all_matched, all_total)),
                "text_all_residual_ratio": round_float(ratio(all_total - all_matched, all_total)),
                "expected_org_text_occurrence_count": sum(expected.values()),
                "foreign_org_text_occurrence_count": sum(foreign.values()),
                "segment_org_text_conformance_ratio": round_float(ratio(expected["text_segment"], segment_matched)),
                "shingle_org_text_conformance_ratio": round_float(ratio(expected["text_word_shingle"], shingle_matched)),
                "org_text_conformance_ratio": round_float(ratio(sum(expected.values()), all_matched)),
                "foreign_org_text_ratio": round_float(ratio(sum(foreign.values()), all_matched)),
                "copy_review_needed_occurrence_count": sum(borrowing.values()),
                "distinct_candidate_count": len(candidate_ids),
                "candidate_status_counts": "|".join(
                    f"{kind}:{status}:{count}" for (kind, status), count in sorted(status_counts.items())
                ),
                "candidate_class_counts": "|".join(
                    f"{kind}:{klass}:{count}" for (kind, klass), count in sorted(class_counts.items())
                ),
                "top_candidate_occurrences": "|".join(f"{key}:{value}" for key, value in top_candidate_ids),
                "coverage_status": "no_text" if all_total == 0 else "measured",
                "interpretation_note": "exact_text_hash_only; residual_is_unexplained_by_v0_text_library_not_proven_original",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows.sort(
        key=lambda row: (
            row["section_code"],
            row["candidate_kind"],
            -safe_int(row["recurrence_object_count"]),
            row["candidate_id"],
        )
    )
    evidence_rows.sort(key=lambda row: (row["candidate_id"], row["object_id"], row["page_number"], row["text_segment_id"]))
    coverage_rows.sort(key=lambda row: (row["section_code"], row["object_id"], row["bundle_id"]))

    write_csv(
        output_dir / "text_element_candidates_v0.csv",
        candidate_rows,
        [
            "candidate_id",
            "schema_version",
            "candidate_class",
            "candidate_kind",
            "candidate_subclass",
            "section_code",
            "primary_entity_kind",
            "entity_hash",
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
            "uc3_signal_status",
            "copy_review_max_section_df_ratio",
            "token_count_mode",
            "char_count_mode",
            "triviality_status",
            "triviality_reason",
            "near_match_status",
            "candidate_status",
            "reliability_note",
            "evidence_occurrence_rows_emitted",
            "evidence_truncated",
        ],
    )
    write_csv(
        output_dir / "text_element_candidate_evidence_v0.csv",
        evidence_rows,
        [
            "candidate_id",
            "section_code",
            "object_id",
            "bundle_id",
            "cohort",
            "crc32",
            "entity_kind",
            "entity_hash",
            "page_number",
            "text_segment_id",
            "source_text_segment_id",
            "shingle_index",
            "token_count",
            "char_count",
            "encoding_status",
            "x1",
            "y1",
            "x2",
            "y2",
            "location_key",
        ],
    )
    write_csv(
        output_dir / "text_element_section_coverage_v0.csv",
        coverage_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "cohort",
            "crc32",
            "text_segment_occurrence_count",
            "text_segment_matched_occurrence_count",
            "text_segment_coverage_ratio",
            "text_segment_residual_count",
            "text_segment_residual_ratio",
            "text_shingle_occurrence_count",
            "text_shingle_matched_occurrence_count",
            "text_shingle_coverage_ratio",
            "text_shingle_residual_count",
            "text_shingle_residual_ratio",
            "text_all_occurrence_count",
            "text_all_matched_occurrence_count",
            "text_all_coverage_ratio",
            "text_all_residual_ratio",
            "expected_org_text_occurrence_count",
            "foreign_org_text_occurrence_count",
            "segment_org_text_conformance_ratio",
            "shingle_org_text_conformance_ratio",
            "org_text_conformance_ratio",
            "foreign_org_text_ratio",
            "copy_review_needed_occurrence_count",
            "distinct_candidate_count",
            "candidate_status_counts",
            "candidate_class_counts",
            "top_candidate_occurrences",
            "coverage_status",
            "interpretation_note",
        ],
    )

    def median(values: list[float]) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    candidate_class_counts = Counter(row["candidate_class"] for row in candidate_rows)
    candidate_kind_counts = Counter(row["candidate_kind"] for row in candidate_rows)
    status_counts = Counter(row["candidate_status"] for row in candidate_rows)
    org_counts = Counter(row["org_distinctiveness_class"] for row in candidate_rows)
    section_kind_counts = Counter((row["section_code"], row["candidate_kind"]) for row in candidate_rows)

    segment_coverage_by_section: dict[str, list[float]] = defaultdict(list)
    shingle_coverage_by_section: dict[str, list[float]] = defaultdict(list)
    all_coverage_by_section: dict[str, list[float]] = defaultdict(list)
    conformance_by_section: dict[str, list[float]] = defaultdict(list)
    for row in coverage_rows:
        if row["coverage_status"] != "measured":
            continue
        section_code = row["section_code"]
        segment_coverage_by_section[section_code].append(float(row["text_segment_coverage_ratio"]))
        shingle_coverage_by_section[section_code].append(float(row["text_shingle_coverage_ratio"]))
        all_coverage_by_section[section_code].append(float(row["text_all_coverage_ratio"]))
        conformance_by_section[section_code].append(float(row["org_text_conformance_ratio"]))

    write_json(
        output_dir / "text_element_library_v0.json",
        {
            "schema_version": "text_element_library_v0",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "export_root": str(export_root),
            "output_dir": str(output_dir),
            "min_objects": min_objects,
            "min_segment_tokens": min_segment_tokens,
            "min_segment_chars": min_segment_chars,
            "shingle_size": shingle_size,
            "max_evidence_per_candidate": max_evidence_per_candidate,
            "copy_review_max_section_df_ratio": copy_review_max_section_df_ratio,
            "cohorts": {name: str(path) for name, path in cohorts},
            "cohort_object_counts": cohort_object_counts,
            "document_count": len(documents),
            "candidate_count": len(candidate_rows),
            "evidence_row_count": len(evidence_rows),
            "evidence_sampling": "per-candidate occurrence sample; full occurrence_count stays in candidate rows",
            "coverage_row_count": len(coverage_rows),
            "skipped_entity_groups_below_min_objects": skipped_small,
            "candidate_kind_counts": dict(sorted(candidate_kind_counts.items())),
            "candidate_class_counts": dict(sorted(candidate_class_counts.items())),
            "candidate_status_counts": dict(sorted(status_counts.items())),
            "org_distinctiveness_counts": dict(sorted(org_counts.items())),
            "section_kind_candidate_counts": {
                f"{section}:{kind}": count for (section, kind), count in sorted(section_kind_counts.items())
            },
            "section_median_text_segment_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(segment_coverage_by_section.items())
            },
            "section_median_text_shingle_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(shingle_coverage_by_section.items())
            },
            "section_median_text_all_coverage_ratio": {
                key: round_float(median(values)) for key, values in sorted(all_coverage_by_section.items())
            },
            "section_median_org_text_conformance_ratio": {
                key: round_float(median(values)) for key, values in sorted(conformance_by_section.items())
            },
            "privacy": "hash-only; raw text is not written",
            "files": {
                "candidates": "text_element_candidates_v0.csv",
                "evidence": "text_element_candidate_evidence_v0.csv",
                "section_coverage": "text_element_section_coverage_v0.csv",
            },
            "modeling_rules": [
                "v0 promotes exact text_segment and text_word_shingle hashes repeated in at least min_objects distinct objects.",
                "text_segment is the primary interpretability signal; text_word_shingle is a phrase-reuse signal.",
                "short text segments are kept as diagnostic_trivial instead of being silently removed.",
                "normative_text means exact text is common across cohorts or too frequent for copy-review.",
                "cross_org_text_bridge is reserved for rare cross-org exact text and needs copy/normative review.",
                "coverage is exact-text-hash-only and must not be read as semantic originality.",
                "cohort labels are applied after extraction and do not change text hashes.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build text element candidates and coverage v0.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-objects", type=int, default=3)
    parser.add_argument("--min-segment-tokens", type=int, default=3)
    parser.add_argument("--min-segment-chars", type=int, default=12)
    parser.add_argument("--shingle-size", type=int, default=5)
    parser.add_argument("--max-evidence-per-candidate", type=int, default=20)
    parser.add_argument(
        "--copy-review-max-section-df-ratio",
        type=float,
        default=0.25,
        help="Cross-org exact text is copy-review only at or below this same-section document-frequency ratio.",
    )
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat for each organization/cohort.",
    )
    args = parser.parse_args()
    build(
        args.base_dir,
        args.export_root,
        args.output_dir,
        args.cohort,
        args.min_objects,
        args.min_segment_tokens,
        args.min_segment_chars,
        args.shingle_size,
        args.max_evidence_per_candidate,
        args.copy_review_max_section_df_ratio,
    )


if __name__ == "__main__":
    main()
