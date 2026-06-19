#!/usr/bin/env python3
"""Apply provenance-first third-party subtraction to GIP near-match outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import build_gip_control_near_match_v0 as near


DEFAULT_PAIRWISE = Path(r"E:\output\DocSpectrum\gip_control_near_match_v0\gip_control_pairwise_near_v0.csv")
DEFAULT_PAGE_MATCHES = Path(
    r"E:\output\DocSpectrum\gip_control_near_match_v0\gip_control_page_best_matches_v0.csv"
)
DEFAULT_PROVENANCE = Path(r"E:\output\DocSpectrum\provenance_assessment_v0\page_provenance_assessment_v0.csv")
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\gip_control_provenance_residual_v0")
DEFAULT_EXPORT_ROOTS = (
    Path(r"E:\output\pdf-structure-explorer\exports"),
    Path(r"E:\output\DocSpectrum\export"),
    Path(r"E:\output\DocSpectrum\export_nk_34"),
    Path(r"E:\output\DocSpectrum\export_nk_34_object_view"),
    Path(r"E:\output\DocSpectrum\export_rpsk35_nk34_object_view"),
)

SECTION_IOS541 = "\u0418\u041e\u04215.4.1"
SECTION_SM = "\u0421\u041c"
LABEL_SECTION_CODE = {
    "normative_form": SECTION_IOS541,
    "shared_technical_content": SECTION_IOS541,
    "estimate_boilerplate": SECTION_SM,
}
THIRD_PARTY_LABELS = tuple(LABEL_SECTION_CODE)


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


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def resolve_bundle_dir(
    bundle_id: str,
    export_roots: tuple[Path, ...],
    cache: dict[str, Path | None],
) -> Path | None:
    if bundle_id in cache:
        return cache[bundle_id]
    for root in export_roots:
        direct = root / bundle_id
        if (direct / "pages.csv").exists():
            cache[bundle_id] = direct
            return direct
        for hit in root.rglob(bundle_id):
            if (hit / "pages.csv").exists():
                cache[bundle_id] = hit
                return hit
    cache[bundle_id] = None
    return None


def page_profile(
    bundle_id: str,
    page_number: int,
    export_roots: tuple[Path, ...],
    bundle_dir_cache: dict[str, Path | None],
    bundle_pages_cache: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if bundle_id not in bundle_pages_cache:
        bundle_dir = resolve_bundle_dir(bundle_id, export_roots, bundle_dir_cache)
        if bundle_dir is None:
            raise FileNotFoundError(f"Bundle not found in export roots: {bundle_id}")
        bundle_pages_cache[bundle_id] = near.build_document_pages(bundle_dir)
    for row in bundle_pages_cache[bundle_id]:
        if int(row["page_number"]) == page_number:
            return row
    raise KeyError(f"Page {page_number} not found in {bundle_id}")


def calibrated_metric_rows(
    provenance_rows: list[dict[str, str]],
    export_roots: tuple[Path, ...],
) -> list[dict[str, Any]]:
    bundle_dir_cache: dict[str, Path | None] = {}
    bundle_pages_cache: dict[str, list[dict[str, Any]]] = {}
    calibrated: list[dict[str, Any]] = []
    for row in provenance_rows:
        label = row.get("review_label", "")
        if row.get("provenance_status") != "expert_assessed" or label not in THIRD_PARTY_LABELS:
            continue
        left_bundle = f"doc_{row['left_crc32']}"
        right_bundle = f"doc_{row['right_crc32']}"
        left_page = page_profile(
            left_bundle,
            int(row["left_page_number"]),
            export_roots,
            bundle_dir_cache,
            bundle_pages_cache,
        )
        right_page = page_profile(
            right_bundle,
            int(row["right_page_number"]),
            export_roots,
            bundle_dir_cache,
            bundle_pages_cache,
        )
        metrics = {
            **near.near_match_score(left_page, right_page),
            **near.pair_content_metrics(left_page, right_page),
        }
        calibrated.append(
            {
                "candidate_id": row["candidate_id"],
                "review_label": label,
                "section_code": LABEL_SECTION_CODE[label],
                **metrics,
            }
        )
    return calibrated


def calibrate_bands(metric_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in metric_rows:
        by_label[row["review_label"]].append(row)

    bands: dict[str, dict[str, Any]] = {}
    for label, rows in sorted(by_label.items()):
        structural = [float(row["page_near_structural_v0_2"]) for row in rows]
        text_segment = [float(row["page_text_segment_jaccard_v0_2"]) for row in rows]
        shingles = [float(row["page_text_word_shingle_jaccard_v0_2"]) for row in rows]
        bands[label] = {
            "review_label": label,
            "section_code": rows[0]["section_code"],
            "assessed_pair_count": len(rows),
            "min_page_near_structural_v0_2": min(structural),
            "median_page_near_structural_v0_2": median(structural),
            "min_page_text_segment_jaccard_v0_2": min(text_segment),
            "median_page_text_segment_jaccard_v0_2": median(text_segment),
            "min_page_text_word_shingle_jaccard_v0_2": min(shingles),
            "median_page_text_word_shingle_jaccard_v0_2": median(shingles),
            "rule_kind_v0_3": "calibrated_minimum_band",
        }
    return bands


def classify_page_match(row: dict[str, str], bands: dict[str, dict[str, Any]]) -> tuple[str, str]:
    section_code = row.get("section_code", "")
    structural = float(row["page_near_structural_v0_2"])
    text_segment = float(row["page_text_segment_jaccard_v0_2"])
    shingles = float(row["page_text_word_shingle_jaccard_v0_2"])

    for label, band in bands.items():
        if section_code != band["section_code"]:
            continue
        if (
            structural >= band["min_page_near_structural_v0_2"]
            and text_segment >= band["min_page_text_segment_jaccard_v0_2"]
            and shingles >= band["min_page_text_word_shingle_jaccard_v0_2"]
        ):
            return label, band["rule_kind_v0_3"]
    return "", ""


def summarize_residual_matches(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {
            "provenance_residual_status_v0_3": "all_excluded",
            "residual_page_match_count_v0_3": 0,
            "residual_page_near_similarity_mean_v0_3": "",
            "residual_page_near_similarity_median_v0_3": "",
            "residual_page_near_shingle_mean_v0_3": "",
            "residual_page_near_shingle_median_v0_3": "",
            "residual_page_near_text_segment_mean_v0_3": "",
            "residual_page_near_text_segment_median_v0_3": "",
            "residual_page_near_exact_share_v0_3": "",
            "residual_page_near_strong_share_v0_3": "",
            "residual_page_near_moderate_share_v0_3": "",
        }

    structural = [float(row["page_near_structural_v0_2"]) for row in rows]
    shingles = [float(row["page_text_word_shingle_jaccard_v0_2"]) for row in rows]
    text_segment = [float(row["page_text_segment_jaccard_v0_2"]) for row in rows]
    exact = [1.0 if row["page_exact_signature_match_v0_2"] == "True" else 0.0 for row in rows]
    strong = [1.0 if float(row["page_near_structural_v0_2"]) >= 0.85 else 0.0 for row in rows]
    moderate = [1.0 if float(row["page_near_structural_v0_2"]) >= 0.70 else 0.0 for row in rows]
    return {
        "provenance_residual_status_v0_3": "measured",
        "residual_page_match_count_v0_3": len(rows),
        "residual_page_near_similarity_mean_v0_3": round_float(mean(structural)),
        "residual_page_near_similarity_median_v0_3": round_float(median(structural)),
        "residual_page_near_shingle_mean_v0_3": round_float(mean(shingles)),
        "residual_page_near_shingle_median_v0_3": round_float(median(shingles)),
        "residual_page_near_text_segment_mean_v0_3": round_float(mean(text_segment)),
        "residual_page_near_text_segment_median_v0_3": round_float(median(text_segment)),
        "residual_page_near_exact_share_v0_3": round_float(mean(exact)),
        "residual_page_near_strong_share_v0_3": round_float(mean(strong)),
        "residual_page_near_moderate_share_v0_3": round_float(mean(moderate)),
    }


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def values(field: str) -> list[float]:
        return [float(row[field]) for row in rows if row[field] not in ("", None)]

    original_shingle = values("page_near_shingle_mean_v0_2")
    residual_shingle = values("residual_page_near_shingle_mean_v0_3")
    original_strong = values("page_near_strong_share_v0_2")
    residual_strong = values("residual_page_near_strong_share_v0_3")
    return {
        "pair_count": len(rows),
        "affected_pair_count_v0_3": sum(
            int(float(row["third_party_excluded_match_count_v0_3"]) > 0) for row in rows
        ),
        "all_excluded_pair_count_v0_3": sum(
            row["provenance_residual_status_v0_3"] == "all_excluded" for row in rows
        ),
        "third_party_excluded_match_count_total_v0_3": sum(
            int(float(row["third_party_excluded_match_count_v0_3"])) for row in rows
        ),
        "page_near_shingle_mean_median_v0_2": round_float(median(original_shingle)) if original_shingle else "",
        "residual_page_near_shingle_mean_median_v0_3": round_float(median(residual_shingle))
        if residual_shingle
        else "",
        "page_near_strong_share_median_v0_2": round_float(median(original_strong)) if original_strong else "",
        "residual_page_near_strong_share_median_v0_3": round_float(median(residual_strong))
        if residual_strong
        else "",
    }


def build_relation_headlines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["cell_kind"], row["relation"])].append(row)
    return [
        {
            "cell_kind": cell_kind,
            "relation": relation,
            **summarize_group(group_rows),
        }
        for (cell_kind, relation), group_rows in sorted(grouped.items())
    ]


def build(
    pairwise_path: Path,
    page_matches_path: Path,
    provenance_path: Path,
    output_dir: Path,
    export_roots: tuple[Path, ...],
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pairwise_rows = read_csv(pairwise_path)
    page_match_rows = read_csv(page_matches_path)
    provenance_rows = read_csv(provenance_path)

    calibrated_rows = calibrated_metric_rows(provenance_rows, export_roots)
    bands = calibrate_bands(calibrated_rows)

    classified_rows: list[dict[str, Any]] = []
    rows_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in page_match_rows:
        label, rule_kind = classify_page_match(row, bands)
        enriched = {
            **row,
            "provenance_label_v0_3": label,
            "provenance_rule_kind_v0_3": rule_kind,
            "provenance_match_status_v0_3": "matched_third_party" if label else "residual_retained",
        }
        classified_rows.append(enriched)
        rows_by_pair[row["pair_id"]].append(enriched)

    pairwise_enriched: list[dict[str, Any]] = []
    relation_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded_label_counts = Counter(
        row["provenance_label_v0_3"] for row in classified_rows if row["provenance_label_v0_3"]
    )

    for row in pairwise_rows:
        pair_id = f"{row['left_bundle_id']}|{row['right_bundle_id']}"
        pair_rows = rows_by_pair[pair_id]
        kept = [candidate for candidate in pair_rows if not candidate["provenance_label_v0_3"]]
        excluded = [candidate for candidate in pair_rows if candidate["provenance_label_v0_3"]]
        residual = summarize_residual_matches(kept)
        excluded_counts = Counter(item["provenance_label_v0_3"] for item in excluded)
        if residual["provenance_residual_status_v0_3"] == "measured":
            residual["provenance_residual_status_v0_3"] = (
                "measured_no_exclusions" if not excluded else "measured_exclusions_applied"
            )
        enriched = {
            **row,
            **residual,
            "third_party_excluded_match_count_v0_3": len(excluded),
            "third_party_excluded_share_v0_3": round_float(
                len(excluded) / len(pair_rows) if pair_rows else 0.0
            ),
            "third_party_excluded_labels_v0_3": "|".join(
                f"{label}:{count}" for label, count in sorted(excluded_counts.items())
            ),
        }
        pairwise_enriched.append(enriched)
        relation_groups[(row["cell_kind"], row["relation"], row["section_code"], row["work_type_key"])].append(
            enriched
        )

    pairwise_enriched.sort(
        key=lambda row: (
            row["cell_kind"],
            row["section_code"],
            row["work_type_key"],
            row["left_object_id"],
            row["right_object_id"],
        )
    )
    classified_rows.sort(
        key=lambda row: (
            row["cell_kind"],
            row["section_code"],
            row["work_type_key"],
            row["pair_id"],
            row["direction"],
            int(row["left_page_number"]),
        )
    )

    summary_rows: list[dict[str, Any]] = []
    for (cell_kind, relation, section_code, work_type_key), rows in sorted(relation_groups.items()):
        summary_rows.append(
            {
                "cell_kind": cell_kind,
                "relation": relation,
                "section_code": section_code,
                "work_type_key": work_type_key,
                **summarize_group(rows),
            }
        )
    relation_headline_rows = build_relation_headlines(pairwise_enriched)

    calibration_rows = [
        {
            "review_label": label,
            "section_code": band["section_code"],
            "assessed_pair_count": band["assessed_pair_count"],
            "min_page_near_structural_v0_2": round_float(band["min_page_near_structural_v0_2"]),
            "median_page_near_structural_v0_2": round_float(band["median_page_near_structural_v0_2"]),
            "min_page_text_segment_jaccard_v0_2": round_float(band["min_page_text_segment_jaccard_v0_2"]),
            "median_page_text_segment_jaccard_v0_2": round_float(band["median_page_text_segment_jaccard_v0_2"]),
            "min_page_text_word_shingle_jaccard_v0_2": round_float(
                band["min_page_text_word_shingle_jaccard_v0_2"]
            ),
            "median_page_text_word_shingle_jaccard_v0_2": round_float(
                band["median_page_text_word_shingle_jaccard_v0_2"]
            ),
            "rule_kind_v0_3": band["rule_kind_v0_3"],
        }
        for label, band in sorted(bands.items())
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "gip_control_page_match_provenance_v0.csv",
        classified_rows,
        list(classified_rows[0]),
    )
    write_csv(
        output_dir / "gip_control_pairwise_provenance_residual_v0.csv",
        pairwise_enriched,
        list(pairwise_enriched[0]),
    )
    write_csv(
        output_dir / "gip_control_provenance_residual_summary_v0.csv",
        summary_rows,
        [
            "cell_kind",
            "relation",
            "section_code",
            "work_type_key",
            "pair_count",
            "affected_pair_count_v0_3",
            "all_excluded_pair_count_v0_3",
            "third_party_excluded_match_count_total_v0_3",
            "page_near_shingle_mean_median_v0_2",
            "residual_page_near_shingle_mean_median_v0_3",
            "page_near_strong_share_median_v0_2",
            "residual_page_near_strong_share_median_v0_3",
        ],
    )
    write_csv(
        output_dir / "gip_control_provenance_residual_headlines_v0.csv",
        relation_headline_rows,
        [
            "cell_kind",
            "relation",
            "pair_count",
            "affected_pair_count_v0_3",
            "all_excluded_pair_count_v0_3",
            "third_party_excluded_match_count_total_v0_3",
            "page_near_shingle_mean_median_v0_2",
            "residual_page_near_shingle_mean_median_v0_3",
            "page_near_strong_share_median_v0_2",
            "residual_page_near_strong_share_median_v0_3",
        ],
    )
    write_csv(
        output_dir / "gip_control_provenance_bands_v0.csv",
        calibration_rows,
        list(calibration_rows[0]),
    )

    payload = {
        "schema_version": "gip_control_provenance_residual_v0",
        "generated_at": generated_at,
        "inputs": {
            "pairwise_near": str(pairwise_path),
            "page_best_matches": str(page_matches_path),
            "provenance_assessment": str(provenance_path),
            "export_roots": [str(root) for root in export_roots],
        },
        "counts": {
            "pair_count": len(pairwise_enriched),
            "page_match_count": len(classified_rows),
            "calibrated_page_pair_count": len(calibrated_rows),
            "third_party_matched_page_count": int(sum(excluded_label_counts.values())),
            "third_party_matched_label_counts": dict(sorted(excluded_label_counts.items())),
            "affected_pair_count_v0_3": sum(
                int(float(row["third_party_excluded_match_count_v0_3"]) > 0) for row in pairwise_enriched
            ),
            "all_excluded_pair_count_v0_3": sum(
                row["provenance_residual_status_v0_3"] == "all_excluded" for row in pairwise_enriched
            ),
        },
        "notes": [
            "Only third-party labels with expert-assessed provenance are used for subtraction.",
            "Current v0 bands are calibrated from reviewed page-pair minima and applied conservatively.",
            "Residual rows retain only page matches not explained by calibrated third-party bands.",
            "Sections without calibrated third-party evidence remain pass-through in this layer.",
        ],
        "relation_headlines": relation_headline_rows,
        "outputs": {
            "page_match_provenance": "gip_control_page_match_provenance_v0.csv",
            "pairwise_residual": "gip_control_pairwise_provenance_residual_v0.csv",
            "summary": "gip_control_provenance_residual_summary_v0.csv",
            "headlines": "gip_control_provenance_residual_headlines_v0.csv",
            "bands": "gip_control_provenance_bands_v0.csv",
        },
    }
    write_json(output_dir / "gip_control_provenance_residual_v0.json", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Subtract calibrated third-party near matches from GIP-control page-match outputs."
    )
    parser.add_argument("--pairwise", type=Path, default=DEFAULT_PAIRWISE)
    parser.add_argument("--page-matches", type=Path, default=DEFAULT_PAGE_MATCHES)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--export-root",
        type=Path,
        action="append",
        dest="export_roots",
        help="Optional extra export roots; defaults cover the current DocSpectrum corpora.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_roots = tuple(args.export_roots) if args.export_roots else DEFAULT_EXPORT_ROOTS
    payload = build(args.pairwise, args.page_matches, args.provenance, args.output_dir, export_roots)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
