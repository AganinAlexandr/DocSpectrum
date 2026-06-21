#!/usr/bin/env python3
"""Build registry-authoritative remark recall for experiment C.

The registry decides clean/remark/unresolved. Content sources provide only
remark count and privacy-safe features. Source-1 baseline and source-2 enriched
results remain separate so new content never rewrites the historical baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from build_expert_quality_experiment_c_v0 import (
    COLUMNS,
    DEFAULT_REGISTRY,
    PLACEHOLDER_DATES,
    anchor_for_expert,
    classify_section,
    date_key,
    expert_hash,
    normalize_object_id,
    normalized_key,
    should_drop_registry_row,
    xlsx_rows,
)
from remark_features import feature_row


DEFAULT_ARENA = Path(
    r"E:\output\DocSpectrum\expert_quality_experiment_c_v0"
    r"\expert_quality_arena_pairs_v0.csv"
)
DEFAULT_SOURCE1 = Path(r"E:\output\fkr\output_analytics_2025.xlsx")
DEFAULT_SOURCE2 = Path(
    r"E:\output\DocSpectrum\download_remark_content_v0"
    r"\download_remark_content_v0.csv"
)
DEFAULT_SOURCE2_INVENTORY = Path(
    r"E:\output\DocSpectrum\download_remark_content_v0"
    r"\download_remark_inventory_v0.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"E:\output\DocSpectrum\expert_quality_remark_recall_v0"
)
REFERENCE = {
    "worklist_count": 199,
    "source1_clean_reviewed": 115,
    "source1_remark_with_content": 52,
    "source1_remark_content_absent": 32,
    "source1_no_registry": 0,
    "source2_found_targets": 26,
    "source2_not_found_targets": 6,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def worklist_from_arena(arena_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    worklist: dict[tuple[str, str], dict[str, Any]] = {}
    for row in arena_rows:
        for side in ("left", "right"):
            key = (row[f"{side}_object_id"], row["section_code"])
            item = worklist.setdefault(
                key,
                {
                    "object_id": key[0],
                    "section_code": key[1],
                    "organization": row["organization"],
                    "work_type": row["work_type"],
                    "group_id": row["group_id"],
                    "anchor_roles": set(),
                    "arena_classes": set(),
                },
            )
            item["anchor_roles"].update(
                role
                for role in row.get(f"{side}_anchor_roles", "").split("|")
                if role
            )
            item["arena_classes"].add(row["arena_class"])
    output = []
    for item in worklist.values():
        output.append(
            {
                **item,
                "anchor_roles": "|".join(sorted(item["anchor_roles"])),
                "arena_classes": "|".join(sorted(item["arena_classes"])),
            }
        )
    return sorted(output, key=lambda row: (row["organization"], row["work_type"], row["section_code"], row["object_id"]))


def registry_status(raw: dict[int, Any]) -> str:
    result_1 = date_key(raw.get(COLUMNS["result_1"]))
    positive = date_key(raw.get(COLUMNS["positive_result"]))
    answer = str(raw.get(COLUMNS["answer_1"]) or "").strip()
    if result_1 and positive and result_1 == positive and not answer:
        return "clean"
    if (result_1 and positive and result_1 != positive) or answer:
        return "remark"
    return "unresolved"


def registry_reviews(
    registry_path: Path,
    worklist_keys: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    output = []
    for raw in xlsx_rows(registry_path, "данные"):
        object_id = normalize_object_id(raw.get(COLUMNS["object_number"]))
        section = classify_section(raw.get(COLUMNS["section"]))
        if (object_id, section) not in worklist_keys:
            continue
        if should_drop_registry_row(raw):
            continue
        name = str(raw.get(COLUMNS["expert_name"]) or "").strip()
        role, quality_class = anchor_for_expert(name)
        output.append(
            {
                "object_id": object_id,
                "section_code": section,
                "expert_hash": expert_hash(name),
                "expert_anchor_role": role,
                "expert_quality_class": quality_class,
                "registry_status": registry_status(raw),
            }
        )
    # Remove exact duplicate review rows, preserving distinct experts.
    unique = {
        (
            row["object_id"],
            row["section_code"],
            row["expert_hash"],
            row["registry_status"],
        ): row
        for row in output
    }
    return list(unique.values())


def normalize_source_section(value: Any) -> str:
    section = str(value or "").strip().upper()
    return "ПОС" if section == "ПОКР" else section


def source1_content(path: Path) -> list[dict[str, Any]]:
    rows = xlsx_rows(path, "Данные", 1)
    if not rows:
        return []
    output = []
    for raw in rows[1:]:
        object_id = normalize_object_id(raw.get(1))
        section = normalize_source_section(raw.get(8))
        expert = str(raw.get(7) or "").strip()
        text = str(raw.get(10) or "").strip()
        if not object_id or section not in {"КР", "ПОС"} or not text:
            continue
        output.append(
            {
                "object_id": object_id,
                "section_code": section,
                "expert_hash": expert_hash(expert),
                "source_kind": "fkr_archive_2025",
                **feature_row(text),
            }
        )
    return output


def content_index(rows: list[dict[str, Any]]) -> tuple[Counter[tuple[str, str, str]], Counter[tuple[str, str]]]:
    exact: Counter[tuple[str, str, str]] = Counter()
    object_section: Counter[tuple[str, str]] = Counter()
    for row in rows:
        key = (row["object_id"], row["section_code"], row.get("expert_hash", ""))
        exact[key] += 1
        object_section[(row["object_id"], row["section_code"])] += 1
    return exact, object_section


def classify_worklist(
    worklist: list[dict[str, str]],
    reviews: list[dict[str, Any]],
    source1_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reviews_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in reviews:
        reviews_by_key[(row["object_id"], row["section_code"])].append(row)
    _, source1_by_object = content_index(source1_rows)
    coverage = []
    for item in worklist:
        key = (item["object_id"], item["section_code"])
        current = reviews_by_key.get(key, [])
        statuses = {row["registry_status"] for row in current}
        count = source1_by_object[key]
        if not current:
            status = "no_registry"
        elif "remark" in statuses:
            status = "remark_with_content" if count else "remark_content_absent"
        elif statuses == {"clean"}:
            status = "clean_reviewed"
            count = 0
        else:
            status = "unresolved"
        coverage.append(
            {
                **item,
                "registry_review_count": len(current),
                "registry_statuses": "|".join(sorted(statuses)),
                "source1_remark_count": count,
                "source1_coverage_status": status,
            }
        )
    return coverage, []


def build_source2_targets(
    reviews: list[dict[str, Any]],
    source1_rows: list[dict[str, Any]],
    worklist: list[dict[str, str]],
) -> list[dict[str, Any]]:
    exact, _ = content_index(source1_rows)
    worklist_by_key = {
        (row["object_id"], row["section_code"]): row for row in worklist
    }
    targets = []
    for review in reviews:
        if review["expert_anchor_role"] not in {
            "ceiling_1_a", "ceiling_1_b", "holdout", "floor_3"
        }:
            continue
        if review["registry_status"] != "remark":
            continue
        key = (review["object_id"], review["section_code"], review["expert_hash"])
        if exact[key]:
            continue
        item = worklist_by_key[(review["object_id"], review["section_code"])]
        targets.append(
            {
                "object_id": review["object_id"],
                "section_code": review["section_code"],
                "expert_hash": review["expert_hash"],
                "expert_anchor_role": review["expert_anchor_role"],
                "organization": item["organization"],
                "work_type": item["work_type"],
            }
        )
    return sorted(
        targets,
        key=lambda row: (
            row["expert_anchor_role"], row["section_code"], row["object_id"]
        ),
    )


def source2_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [dict(row) for row in read_csv(path)]


def review_recall_rows(
    worklist: list[dict[str, str]],
    reviews: list[dict[str, Any]],
    source1_rows: list[dict[str, Any]],
    source2_content: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    worklist_by_key = {
        (row["object_id"], row["section_code"]): row for row in worklist
    }
    source1_exact, _ = content_index(source1_rows)
    source2_counts: Counter[tuple[str, str, str]] = Counter(
        (row["object_id"], row["section_code"], row.get("expert_hash", ""))
        for row in source2_content
    )
    output = []
    for review in reviews:
        key = (review["object_id"], review["section_code"])
        if key not in worklist_by_key:
            continue
        baseline_count: int | None
        enriched_count: int | None
        source = ""
        if review["registry_status"] == "clean":
            baseline_count = 0
            enriched_count = 0
            source = "registry_clean"
        elif review["registry_status"] == "remark":
            exact_key = (*key, review["expert_hash"])
            baseline_count = source1_exact[exact_key] or None
            enriched_count = baseline_count
            source = "source1_exact" if baseline_count is not None else ""
            source2_key = (*key, review["expert_hash"])
            if enriched_count is None and source2_counts[source2_key]:
                enriched_count = source2_counts[source2_key]
                source = "source2_exact_registry_reviewer"
        else:
            baseline_count = None
            enriched_count = None
        item = worklist_by_key[key]
        output.append(
            {
                **review,
                "organization": item["organization"],
                "work_type": item["work_type"],
                "group_id": item["group_id"],
                "baseline_remark_count": "" if baseline_count is None else baseline_count,
                "enriched_remark_count": "" if enriched_count is None else enriched_count,
                "content_assignment_source": source,
            }
        )
    return output


def cell_recall(review_rows: list[dict[str, Any]], count_field: str, layer: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in review_rows:
        value = row[count_field]
        role = row["expert_anchor_role"]
        if value == "" or role not in {"ceiling_1_a", "ceiling_1_b", "holdout", "floor_3"}:
            continue
        bucket = "ceiling" if role.startswith("ceiling_") else role
        grouped[(row["organization"], row["work_type"], row["section_code"])][bucket].append(float(value))
    output = []
    for cell, roles in sorted(grouped.items()):
        ceiling = roles["ceiling"]
        holdout = roles["holdout"]
        floor = roles["floor_3"]
        ceiling_mean = mean(ceiling) if ceiling else None
        holdout_mean = mean(holdout) if holdout else None
        recall = (
            holdout_mean / ceiling_mean
            if ceiling_mean not in (None, 0) and holdout_mean is not None
            else None
        )
        output.append(
            {
                "layer": layer,
                "organization": cell[0],
                "work_type": cell[1],
                "section_code": cell[2],
                "ceiling_section_count": len(ceiling),
                "ceiling_remarks_per_section": "" if ceiling_mean is None else round(ceiling_mean, 4),
                "holdout_section_count": len(holdout),
                "holdout_remarks_per_section": "" if holdout_mean is None else round(holdout_mean, 4),
                "floor_section_count": len(floor),
                "floor_remarks_per_section": "" if not floor else round(mean(floor), 4),
                "holdout_recall_vs_ceiling_v0": "" if recall is None else round(recall, 4),
                "recall_status": "measured" if recall is not None else "insufficient_ceiling_or_holdout",
            }
        )
    return output


def build(
    arena_path: Path,
    registry_path: Path,
    source1_path: Path,
    source2_path: Path,
    source2_inventory_path: Path,
    output_dir: Path,
    assert_reference: bool = False,
) -> dict[str, Any]:
    worklist = worklist_from_arena(read_csv(arena_path))
    worklist_keys = {(row["object_id"], row["section_code"]) for row in worklist}
    reviews = registry_reviews(registry_path, worklist_keys)
    source1 = source1_content(source1_path)
    coverage, _ = classify_worklist(worklist, reviews, source1)
    targets = build_source2_targets(reviews, source1, worklist)
    source2 = source2_rows(source2_path)
    review_rows = review_recall_rows(worklist, reviews, source1, source2)
    cells = cell_recall(review_rows, "baseline_remark_count", "source1_baseline")
    cells += cell_recall(review_rows, "enriched_remark_count", "enriched")

    coverage_counts = Counter(row["source1_coverage_status"] for row in coverage)
    source2_inventory = read_csv(source2_inventory_path) if source2_inventory_path.exists() else []
    source2_found = sum(bool(row.get("source_file")) for row in source2_inventory)
    source2_not_found = sum(row.get("extract_status") == "not_found" for row in source2_inventory)
    actual = {
        "worklist_count": len(worklist),
        "source1_clean_reviewed": coverage_counts["clean_reviewed"],
        "source1_remark_with_content": coverage_counts["remark_with_content"],
        "source1_remark_content_absent": coverage_counts["remark_content_absent"],
        "source1_no_registry": coverage_counts["no_registry"],
        "source2_found_targets": source2_found,
        "source2_not_found_targets": source2_not_found,
    }
    reference_check = {
        key: {
            "expected": expected,
            "actual": actual[key],
            "status": "matched" if actual[key] == expected else "changed",
        }
        for key, expected in REFERENCE.items()
    }
    if assert_reference:
        changed = {
            key: row for key, row in reference_check.items() if row["status"] != "matched"
        }
        if changed:
            raise ValueError(f"Remark recall reference changed: {changed}")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "remark_recall_worklist_v0.csv", coverage, list(coverage[0]))
    write_csv(output_dir / "source2_targets_v0.csv", targets, list(targets[0]))
    write_csv(output_dir / "remark_recall_reviews_v0.csv", review_rows, list(review_rows[0]))
    write_csv(output_dir / "remark_recall_cells_v0.csv", cells, list(cells[0]))

    review_by_exact = {
        (row["object_id"], row["section_code"], row["expert_hash"]): row
        for row in reviews
    }
    feature_rows = []
    for row in source1 + source2:
        exact_key = (
            row["object_id"],
            row["section_code"],
            row.get("expert_hash", ""),
        )
        review = review_by_exact.get(exact_key)
        if exact_key[:2] not in worklist_keys or not review:
            continue
        if review["registry_status"] != "remark":
            continue
        feature_rows.append(
            {
                "object_id": row["object_id"],
                "section_code": row["section_code"],
                "expert_hash": row.get("expert_hash", ""),
                "expert_anchor_role": review["expert_anchor_role"],
                "source_kind": row.get("source_kind", ""),
                "remark_hash": row.get("remark_hash", ""),
                "char_count": row.get("char_count", ""),
                "word_count": row.get("word_count", ""),
                "primary_category_v0": row.get("primary_category_v0", ""),
                "categories_v0": row.get("categories_v0", ""),
                "depth_class_v0": row.get("depth_class_v0", ""),
                "depth_reason_codes_v0": row.get("depth_reason_codes_v0", ""),
            }
        )
    feature_fields = list(feature_rows[0]) if feature_rows else ["object_id", "section_code"]
    write_csv(output_dir / "remark_features_v0.csv", feature_rows, feature_fields)

    quality_counts: Counter[tuple[str, str, str]] = Counter()
    for row in feature_rows:
        quality_counts[
            (
                row["expert_anchor_role"],
                row["depth_class_v0"],
                row["primary_category_v0"],
            )
        ] += 1
    quality_rows = [
        {
            "expert_anchor_role": key[0],
            "depth_class_v0": key[1],
            "primary_category_v0": key[2],
            "remark_count": count,
        }
        for key, count in sorted(quality_counts.items())
    ]
    write_csv(
        output_dir / "remark_quality_by_role_v0.csv",
        quality_rows,
        [
            "expert_anchor_role",
            "depth_class_v0",
            "primary_category_v0",
            "remark_count",
        ],
    )

    recurrence: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"documents": set(), "roles": set(), "sources": set()}
    )
    for row in feature_rows:
        item = recurrence[row["remark_hash"]]
        item["documents"].add(f"{row['object_id']}:{row['section_code']}")
        item["roles"].add(row["expert_anchor_role"])
        item["sources"].add(row["source_kind"])
    recurrence_rows = [
        {
            "remark_hash": remark_hash,
            "document_count": len(values["documents"]),
            "role_count": len(values["roles"]),
            "expert_anchor_roles": "|".join(sorted(values["roles"])),
            "source_kinds": "|".join(sorted(values["sources"])),
            "recurrence_status": (
                "recurrent_exact_text"
                if len(values["documents"]) >= 2
                else "single_document"
            ),
        }
        for remark_hash, values in sorted(
            recurrence.items(),
            key=lambda item: (-len(item[1]["documents"]), item[0]),
        )
    ]
    write_csv(
        output_dir / "remark_recurrence_v0.csv",
        recurrence_rows,
        [
            "remark_hash",
            "document_count",
            "role_count",
            "expert_anchor_roles",
            "source_kinds",
            "recurrence_status",
        ],
    )

    summary = {
        "schema_version": "expert_quality_remark_recall_v0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            **actual,
            "registry_review_row_count": len(reviews),
            "source1_content_row_count": len(source1),
            "source2_content_row_count": len(source2),
            "registry_gated_feature_row_count": len(feature_rows),
            "distinct_remark_hash_count": len(recurrence_rows),
            "recall_cell_row_count": len(cells),
        },
        "reference_check": reference_check,
        "interpretation": {
            "outcome_authority": "registry_only",
            "content_sources": "content_and_count_only",
            "baseline": "source1_only",
            "enriched": "source1_plus_unambiguous_source2",
            "count_recall": "v0_proxy_count_not_quality",
            "depth": "heuristic_candidate_not_ground_truth",
        },
    }
    (output_dir / "expert_quality_remark_recall_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build experiment C remark recall.")
    parser.add_argument("--arena", type=Path, default=DEFAULT_ARENA)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--source1", type=Path, default=DEFAULT_SOURCE1)
    parser.add_argument("--source2", type=Path, default=DEFAULT_SOURCE2)
    parser.add_argument("--source2-inventory", type=Path, default=DEFAULT_SOURCE2_INVENTORY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--assert-reference", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build(
        args.arena,
        args.registry,
        args.source1,
        args.source2,
        args.source2_inventory,
        args.output_dir,
        args.assert_reference,
    )
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
