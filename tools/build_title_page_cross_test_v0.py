#!/usr/bin/env python3
"""Compare title-page element spectra across document cohorts.

Title-page labels are an external profile/eval input joined by CRC32. Core page
features remain domain-neutral. Pair labels are applied only after similarity
features are calculated.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_BASE_DIR = Path(r"E:\output\DocSpectrum\element_base_v0_rpsk35_nk34")
DEFAULT_REGISTRY = Path(r"E:\repos\checker-shared-project\registries\title_pages_by_crc.csv")
DEFAULT_NK_INPUT = Path(
    r"E:\repos\checker-shared-project\projects\docspectrum\inputs\title_pages_nk_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\title_page_cross_test_v0")
PROFILE_SCOPES = ("title_anchor", "cover_zone", "body")
COUNT_FEATURES = ("text_count", "line_count", "frame_count", "image_count", "table_count", "other_count")


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


def load_title_reference(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    reference: dict[str, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()
    for path in paths:
        source_name = path.name
        for row in read_reference_csv(path):
            crc32 = (row.get("crc32") or "").strip().lower()
            if not crc32:
                continue
            incoming = {
                "crc32": crc32,
                "file_name": row.get("file_name", ""),
                "cover_pages": parse_pages(row.get("cover_pages", "")),
                "title_anchor_pages": parse_pages(row.get("title_anchor_pages", "")),
                "anomaly": row.get("anomaly", ""),
                "confidence": row.get("confidence", ""),
                "reference_source": source_name,
            }
            existing = reference.get(crc32)
            if existing and (
                existing["cover_pages"] != incoming["cover_pages"]
                or existing["title_anchor_pages"] != incoming["title_anchor_pages"]
            ):
                raise ValueError(f"Conflicting title reference rows for CRC32 {crc32}")
            reference[crc32] = incoming
            source_counts[source_name] += 1
    return reference, dict(sorted(source_counts.items()))


def multiset_jaccard(left: Counter[str], right: Counter[str]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    intersection = sum(min(left[key], right[key]) for key in keys)
    union = sum(max(left[key], right[key]) for key in keys)
    return intersection / union if union else 0.0


def ratio_feature_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    values = []
    for feature in COUNT_FEATURES:
        a = left[feature]
        b = right[feature]
        if a == 0.0 and b == 0.0:
            continue
        values.append(min(a, b) / max(a, b))
    return sum(values) / len(values) if values else 1.0


def composition_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    return sum(min(left[f"{feature}_share"], right[f"{feature}_share"]) for feature in COUNT_FEATURES)


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


def build_profile(
    document: dict[str, str],
    pages: list[dict[str, str]],
    selected_pages: set[int],
    scope: str,
    reference: dict[str, Any],
    cohort: str,
) -> dict[str, Any] | None:
    selected = [row for row in pages if safe_int(row["page_number"]) in selected_pages]
    if not selected:
        return None

    totals = Counter()
    page_signatures: Counter[str] = Counter()
    page_sizes: Counter[str] = Counter()
    for row in selected:
        element_count = safe_int(row["element_count"])
        known_count = 0
        for feature in ("text_count", "line_count", "frame_count", "image_count", "table_count"):
            count = safe_int(row[feature])
            totals[feature] += count
            known_count += count
        totals["other_count"] += max(0, element_count - known_count)
        totals["element_count"] += element_count
        if row.get("page_signature"):
            page_signatures[row["page_signature"]] += 1
        if row.get("page_size_key"):
            page_sizes[row["page_size_key"]] += 1

    page_count = len(selected)
    component_total = sum(totals[feature] for feature in COUNT_FEATURES)
    profile: dict[str, Any] = {
        "object_id": document["object_id"],
        "bundle_id": document["bundle_id"],
        "section_code": document["section_code"],
        "crc32": document["crc32"].lower(),
        "cohort": cohort,
        "scope": scope,
        "selected_pages": "|".join(str(page) for page in sorted(selected_pages)),
        "selected_page_count": page_count,
        "reference_source": reference["reference_source"],
        "title_confidence": reference["confidence"],
        "title_anomaly": reference["anomaly"],
        "page_signatures": page_signatures,
        "page_sizes": page_sizes,
    }
    for feature in COUNT_FEATURES:
        profile[feature] = totals[feature] / page_count
        profile[f"{feature}_share"] = totals[feature] / component_total if component_total else 0.0
    profile["elements_per_page"] = totals["element_count"] / page_count
    return profile


def similarity_row(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    feature_similarity = ratio_feature_similarity(left, right)
    composition = composition_similarity(left, right)
    page_size = multiset_jaccard(left["page_sizes"], right["page_sizes"])
    exact_page = multiset_jaccard(left["page_signatures"], right["page_signatures"])
    combined = 0.6 * feature_similarity + 0.3 * composition + 0.1 * page_size
    combined_no_size = (0.6 * feature_similarity + 0.3 * composition) / 0.9
    pair_type = "within_org" if left["cohort"] == right["cohort"] else "cross_org"
    cohort_pair = "|".join(sorted((left["cohort"], right["cohort"])))
    section_relation = "same_section" if left["section_code"] == right["section_code"] else "different_section"
    return {
        "scope": left["scope"],
        "object_id_a": left["object_id"],
        "bundle_id_a": left["bundle_id"],
        "section_code_a": left["section_code"],
        "crc32_a": left["crc32"],
        "cohort_a": left["cohort"],
        "object_id_b": right["object_id"],
        "bundle_id_b": right["bundle_id"],
        "section_code_b": right["section_code"],
        "crc32_b": right["crc32"],
        "cohort_b": right["cohort"],
        "pair_type": pair_type,
        "cohort_pair": cohort_pair,
        "section_relation": section_relation,
        "feature_ratio_similarity": round_float(feature_similarity),
        "composition_similarity": round_float(composition),
        "page_size_jaccard": round_float(page_size),
        "exact_page_signature_jaccard": round_float(exact_page),
        "title_element_similarity_v0": round_float(combined),
        "title_element_similarity_no_size_v0": round_float(combined_no_size),
    }


def build(
    base_dir: Path,
    registry_paths: list[Path],
    output_dir: Path,
    cohorts: list[tuple[str, Path]],
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    object_to_cohort, cohort_object_counts = load_object_cohorts(cohorts)
    reference, reference_source_counts = load_title_reference(registry_paths)
    documents = read_csv(base_dir / "documents_index.csv")
    page_rows = read_csv(base_dir / "page_signatures_v0.csv")
    pages_by_doc: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in page_rows:
        pages_by_doc[(row["object_id"], row["bundle_id"])].append(row)

    profiles_by_scope: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_reference = []
    non_high_reference = []
    missing_pages = []
    for document in documents:
        crc32 = document["crc32"].lower()
        title_ref = reference.get(crc32)
        if title_ref is None:
            missing_reference.append(crc32)
            continue
        if title_ref["confidence"] != "high":
            non_high_reference.append(crc32)
            continue
        doc_pages = pages_by_doc[(document["object_id"], document["bundle_id"])]
        available_pages = {safe_int(row["page_number"]) for row in doc_pages}
        scopes = {
            "title_anchor": title_ref["title_anchor_pages"],
            "cover_zone": title_ref["cover_pages"],
            "body": available_pages - title_ref["cover_pages"],
        }
        for scope, selected_pages in scopes.items():
            profile = build_profile(
                document,
                doc_pages,
                selected_pages,
                scope,
                title_ref,
                object_to_cohort.get(document["object_id"], "UNKNOWN"),
            )
            if profile is None:
                missing_pages.append(f"{crc32}:{scope}")
                continue
            profiles_by_scope[scope].append(profile)

    profile_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for scope in PROFILE_SCOPES:
        profiles = sorted(
            profiles_by_scope[scope],
            key=lambda row: (row["cohort"], row["section_code"], row["object_id"], row["bundle_id"]),
        )
        for profile in profiles:
            profile_rows.append(
                {
                    **{key: value for key, value in profile.items() if key not in {"page_signatures", "page_sizes"}},
                    "page_signature_count": sum(profile["page_signatures"].values()),
                    "unique_page_signature_count": len(profile["page_signatures"]),
                    "page_size_keys": "|".join(
                        f"{key}:{value}" for key, value in sorted(profile["page_sizes"].items())
                    ),
                }
            )
        pair_rows.extend(similarity_row(left, right) for left, right in combinations(profiles, 2))

    summary_values: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: {"with_size": [], "no_size": []}
    )
    for row in pair_rows:
        values = summary_values[(row["scope"], row["pair_type"], row["section_relation"])]
        values["with_size"].append(float(row["title_element_similarity_v0"]))
        values["no_size"].append(float(row["title_element_similarity_no_size_v0"]))

    summary_rows = []
    for (scope, pair_type, section_relation), metrics in sorted(summary_values.items()):
        values = metrics["with_size"]
        no_size_values = metrics["no_size"]
        summary_rows.append(
            {
                "scope": scope,
                "pair_type": pair_type,
                "section_relation": section_relation,
                "pair_count": len(values),
                "similarity_p10": round_float(quantile(values, 0.1)),
                "similarity_median": round_float(median(values)),
                "similarity_p90": round_float(quantile(values, 0.9)),
                "similarity_no_size_p10": round_float(quantile(no_size_values, 0.1)),
                "similarity_no_size_median": round_float(median(no_size_values)),
                "similarity_no_size_p90": round_float(quantile(no_size_values, 0.9)),
            }
        )

    nearest_rows = []
    for scope in PROFILE_SCOPES:
        profiles = profiles_by_scope[scope]
        for profile in profiles:
            candidates_by_metric: dict[str, list[tuple[float, dict[str, Any], dict[str, Any]]]] = {
                "with_size": [],
                "no_size": [],
            }
            for other in profiles:
                if other["crc32"] == profile["crc32"]:
                    continue
                row = similarity_row(profile, other)
                candidates_by_metric["with_size"].append(
                    (float(row["title_element_similarity_v0"]), other, row)
                )
                candidates_by_metric["no_size"].append(
                    (float(row["title_element_similarity_no_size_v0"]), other, row)
                )
            for metric, candidates in candidates_by_metric.items():
                if not candidates:
                    continue
                candidates.sort(key=lambda item: (-item[0], item[1]["crc32"]))
                score, nearest, row = candidates[0]
                nearest_rows.append(
                    {
                        "scope": scope,
                        "similarity_metric": metric,
                        "object_id": profile["object_id"],
                        "bundle_id": profile["bundle_id"],
                        "section_code": profile["section_code"],
                        "crc32": profile["crc32"],
                        "cohort": profile["cohort"],
                        "nearest_object_id": nearest["object_id"],
                        "nearest_bundle_id": nearest["bundle_id"],
                        "nearest_section_code": nearest["section_code"],
                        "nearest_crc32": nearest["crc32"],
                        "nearest_cohort": nearest["cohort"],
                        "nearest_pair_type": row["pair_type"],
                        "nearest_section_relation": row["section_relation"],
                        "nearest_similarity": round_float(score),
                    }
                )

    nearest_counts = Counter(
        (row["scope"], row["similarity_metric"], row["nearest_pair_type"]) for row in nearest_rows
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "title_page_profiles_v0.csv",
        profile_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "crc32",
            "cohort",
            "scope",
            "selected_pages",
            "selected_page_count",
            "reference_source",
            "title_confidence",
            "title_anomaly",
            "elements_per_page",
            *COUNT_FEATURES,
            *(f"{feature}_share" for feature in COUNT_FEATURES),
            "page_signature_count",
            "unique_page_signature_count",
            "page_size_keys",
        ],
    )
    write_csv(
        output_dir / "title_page_pairs_v0.csv",
        pair_rows,
        [
            "scope",
            "object_id_a",
            "bundle_id_a",
            "section_code_a",
            "crc32_a",
            "cohort_a",
            "object_id_b",
            "bundle_id_b",
            "section_code_b",
            "crc32_b",
            "cohort_b",
            "pair_type",
            "cohort_pair",
            "section_relation",
            "feature_ratio_similarity",
            "composition_similarity",
            "page_size_jaccard",
            "exact_page_signature_jaccard",
            "title_element_similarity_v0",
            "title_element_similarity_no_size_v0",
        ],
    )
    write_csv(
        output_dir / "title_page_similarity_summary_v0.csv",
        summary_rows,
        [
            "scope",
            "pair_type",
            "section_relation",
            "pair_count",
            "similarity_p10",
            "similarity_median",
            "similarity_p90",
            "similarity_no_size_p10",
            "similarity_no_size_median",
            "similarity_no_size_p90",
        ],
    )
    write_csv(
        output_dir / "title_page_nearest_neighbors_v0.csv",
        nearest_rows,
        [
            "scope",
            "similarity_metric",
            "object_id",
            "bundle_id",
            "section_code",
            "crc32",
            "cohort",
            "nearest_object_id",
            "nearest_bundle_id",
            "nearest_section_code",
            "nearest_crc32",
            "nearest_cohort",
            "nearest_pair_type",
            "nearest_section_relation",
            "nearest_similarity",
        ],
    )
    write_json(
        output_dir / "title_page_cross_test_v0.json",
        {
            "schema_version": "title_page_cross_test_v0",
            "generated_at": generated_at,
            "base_dir": str(base_dir),
            "registry_paths": [str(path) for path in registry_paths],
            "output_dir": str(output_dir),
            "document_count": len(documents),
            "reference_row_count": len(reference),
            "reference_source_counts": reference_source_counts,
            "cohort_object_counts": cohort_object_counts,
            "profile_counts": {scope: len(profiles_by_scope[scope]) for scope in PROFILE_SCOPES},
            "pair_count": len(pair_rows),
            "missing_reference_count": len(missing_reference),
            "non_high_reference_count": len(non_high_reference),
            "missing_profile_count": len(missing_pages),
            "missing_reference_crc32": sorted(missing_reference),
            "non_high_reference_crc32": sorted(non_high_reference),
            "missing_profiles": sorted(missing_pages),
            "nearest_neighbor_counts": {
                f"{scope}:{metric}:{pair_type}": count
                for (scope, metric, pair_type), count in sorted(nearest_counts.items())
            },
            "similarity_summary": summary_rows,
            "files": {
                "profiles": "title_page_profiles_v0.csv",
                "pairs": "title_page_pairs_v0.csv",
                "summary": "title_page_similarity_summary_v0.csv",
                "nearest_neighbors": "title_page_nearest_neighbors_v0.csv",
            },
            "modeling_rules": [
                "title labels are external eval/profile inputs joined by CRC32; page features remain core-neutral.",
                "cohort labels are applied after similarity features are calculated.",
                "title_anchor compares detected title pages; cover_zone compares all front-matter pages; body excludes cover_zone.",
                "title_element_similarity_v0 combines per-page feature ratios, element composition and page-size overlap.",
                "title_element_similarity_no_size_v0 removes page size as a sensitivity check.",
                "exact page-signature Jaccard remains diagnostic because exact page hashes are strict.",
                "current ground truth tests organization separation only; GIP attribution needs GIP labels.",
            ],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build title-page cross-organization element-spectrum test v0.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--registry", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--cohort",
        type=parse_cohort,
        action="append",
        required=True,
        help="Cohort in NAME=EXPORT_ROOT format. Repeat for each organization/cohort.",
    )
    args = parser.parse_args()
    registry_paths = args.registry or [DEFAULT_REGISTRY, DEFAULT_NK_INPUT]
    build(args.base_dir, registry_paths, args.output_dir, args.cohort)


if __name__ == "__main__":
    main()
