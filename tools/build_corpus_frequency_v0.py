#!/usr/bin/env python3
"""Build a corpus-frequency library for typicality/originality analysis.

This script is section-to-library oriented, not pairwise A-to-B comparison.
It builds:

- a section library index;
- an extracted-entity frequency library;
- per-section typicality/originality summaries.

Raw text is not written to artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from text_features import normalize_text, sha1_text, text_tokens, word_shingles


TEXT_ENTITY_KINDS = ("text_segment", "text_word_shingle")
STRUCTURAL_ENTITY_KINDS = ("page_signature", "table_layout_signature", "table_content_signature")
TABLE_CELL_ENTITY_KINDS = ("table_cell_text",)
ENTITY_KINDS = TEXT_ENTITY_KINDS + STRUCTURAL_ENTITY_KINDS + TABLE_CELL_ENTITY_KINDS


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


def safe_int(value: Any) -> int:
    try:
        if value in ("", None):
            return 0
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def round_float(value: float, digits: int = 4) -> float:
    return round(value, digits)


def entity_key(entity_kind: str, entity_hash: str) -> tuple[str, str]:
    return entity_kind, entity_hash


def classify_bucket(section_df: int, section_document_count: int, typical_ratio: float) -> str:
    if section_document_count < 2:
        return "low_population"
    if section_df <= 1:
        return "original"
    ratio = section_df / section_document_count
    if ratio >= typical_ratio:
        return "typical"
    return "shared_rare"


def empty_entity_counters() -> dict[str, Counter[str]]:
    return {kind: Counter() for kind in ENTITY_KINDS}


def load_structural_entities(base_dir: Path) -> dict[tuple[str, str], dict[str, Counter[str]]]:
    entities_by_doc: dict[tuple[str, str], dict[str, Counter[str]]] = defaultdict(empty_entity_counters)

    for row in read_csv(base_dir / "page_signatures_v0.csv"):
        signature = row.get("page_signature")
        if signature:
            entities_by_doc[(row["object_id"], row["bundle_id"])]["page_signature"][signature] += 1

    for row in read_csv(base_dir / "table_signatures_v0.csv"):
        doc_key = (row["object_id"], row["bundle_id"])
        layout_signature = row.get("layout_signature")
        if layout_signature:
            entities_by_doc[doc_key]["table_layout_signature"][layout_signature] += 1
        content_signature = row.get("content_sha1")
        if content_signature:
            entities_by_doc[doc_key]["table_content_signature"][content_signature] += 1

    return entities_by_doc


def build_document_text_entities(export_root: Path, object_id: str, bundle_id: str) -> dict[str, Counter[str]]:
    path = export_root / object_id / bundle_id / "text_segments.csv"
    counters = empty_entity_counters()
    if not path.exists():
        return counters

    rows = read_csv(path)
    for row in rows:
        normalized = normalize_text(row.get("normalized_text") or row.get("text_value") or "")
        if not normalized:
            continue
        counters["text_segment"][sha1_text(normalized)] += 1
        tokens = text_tokens(normalized)
        for shingle in word_shingles(tokens):
            counters["text_word_shingle"][sha1_text(shingle)] += 1
    return counters


def add_document_table_cell_entities(
    counters: dict[str, Counter[str]],
    export_root: Path,
    object_id: str,
    bundle_id: str,
) -> None:
    path = export_root / object_id / bundle_id / "table_cells.csv"
    if not path.exists():
        return

    for row in read_csv(path):
        normalized = normalize_text(row.get("text_value") or "")
        if normalized:
            counters["table_cell_text"][sha1_text(normalized)] += 1


def build_document_entities(
    export_root: Path,
    object_id: str,
    bundle_id: str,
    structural_entities: dict[tuple[str, str], dict[str, Counter[str]]],
) -> dict[str, Counter[str]]:
    counters = build_document_text_entities(export_root, object_id, bundle_id)
    doc_key = (object_id, bundle_id)
    for entity_kind in STRUCTURAL_ENTITY_KINDS:
        counters[entity_kind].update(structural_entities.get(doc_key, {}).get(entity_kind, Counter()))
    add_document_table_cell_entities(counters, export_root, object_id, bundle_id)
    return counters


def build(base_dir: Path, export_root: Path, output_dir: Path, typical_ratio: float) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    documents = read_csv(base_dir / "documents_index.csv")
    structural_entities = load_structural_entities(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    section_document_counts = Counter(row["section_code"] for row in documents)
    document_count = len(documents)

    section_library_rows: list[dict[str, Any]] = []
    document_entities: dict[tuple[str, str], dict[str, Counter[str]]] = {}
    global_df: Counter[tuple[str, str]] = Counter()
    section_df: Counter[tuple[str, str, str]] = Counter()
    occurrence_total: Counter[tuple[str, str]] = Counter()
    section_documents_by_entity: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for row in documents:
        doc_key = (row["object_id"], row["bundle_id"])
        section_code = row["section_code"]
        entities = build_document_entities(export_root, *doc_key, structural_entities)
        document_entities[doc_key] = entities

        section_library_rows.append(
            {
                "object_id": row["object_id"],
                "bundle_id": row["bundle_id"],
                "section_code": section_code,
                "section_role": row["section_role"],
                "crc32": row["crc32"],
                "file_name": row["file_name"],
                "page_count": row["page_count"],
                "text_segment_count": row["text_segment_count"],
                "total_text_chars": row["total_text_chars"],
                "total_text_words": row["total_text_words"],
                "broken_encoding_count": row["broken_encoding_count"],
            }
        )

        for entity_kind, counter in entities.items():
            for entity_hash in counter:
                global_df[entity_key(entity_kind, entity_hash)] += 1
                section_df[(section_code, entity_kind, entity_hash)] += 1
                section_documents_by_entity[(section_code, entity_kind, entity_hash)].add(
                    f"{row['object_id']}:{row['bundle_id']}"
                )
            for entity_hash, count in counter.items():
                occurrence_total[entity_key(entity_kind, entity_hash)] += count

    write_csv(
        output_dir / "section_library_v0.csv",
        section_library_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "section_role",
            "crc32",
            "file_name",
            "page_count",
            "text_segment_count",
            "total_text_chars",
            "total_text_words",
            "broken_encoding_count",
        ],
    )

    entity_rows: list[dict[str, Any]] = []
    for (section_code, entity_kind, entity_hash), sec_df in section_df.items():
        glob_df = global_df[entity_key(entity_kind, entity_hash)]
        sec_n = section_document_counts[section_code]
        bucket = classify_bucket(sec_df, sec_n, typical_ratio)
        section_documents = sorted(section_documents_by_entity[(section_code, entity_kind, entity_hash)])
        entity_rows.append(
            {
                "section_code": section_code,
                "entity_kind": entity_kind,
                "entity_hash": entity_hash,
                "section_df": sec_df,
                "section_document_count": sec_n,
                "section_df_ratio": round_float(sec_df / sec_n if sec_n else 0.0),
                "section_idf": round_float(math.log((sec_n + 1) / (sec_df + 1)) + 1.0),
                "global_df": glob_df,
                "global_document_count": document_count,
                "global_df_ratio": round_float(glob_df / document_count if document_count else 0.0),
                "global_idf": round_float(math.log((document_count + 1) / (glob_df + 1)) + 1.0),
                "occurrence_count": occurrence_total[entity_key(entity_kind, entity_hash)],
                "frequency_bucket": bucket,
                "section_documents": "|".join(section_documents),
                "section_objects": "|".join(sorted({item.split(":", 1)[0] for item in section_documents})),
            }
        )
    entity_rows.sort(
        key=lambda row: (
            row["section_code"],
            row["entity_kind"],
            -safe_int(row["section_df"]),
            row["entity_hash"],
        )
    )
    write_csv(
        output_dir / "entity_frequency_v0.csv",
        entity_rows,
        [
            "section_code",
            "entity_kind",
            "entity_hash",
            "section_df",
            "section_document_count",
            "section_df_ratio",
            "section_idf",
            "global_df",
            "global_document_count",
            "global_df_ratio",
            "global_idf",
            "occurrence_count",
            "frequency_bucket",
            "section_documents",
            "section_objects",
        ],
    )

    entity_meta = {
        (row["section_code"], row["entity_kind"], row["entity_hash"]): row
        for row in entity_rows
    }
    assessment_rows: list[dict[str, Any]] = []
    for doc in section_library_rows:
        doc_key = (doc["object_id"], doc["bundle_id"])
        section_code = doc["section_code"]
        for entity_kind, counter in document_entities[doc_key].items():
            totals = Counter()
            weighted_idf_sum = 0.0
            occurrence_count = sum(counter.values())
            unique_count = len(counter)
            for entity_hash, count in counter.items():
                meta = entity_meta[(section_code, entity_kind, entity_hash)]
                bucket = meta["frequency_bucket"]
                totals[bucket] += count
                weighted_idf_sum += float(meta["section_idf"]) * count
            assessment_rows.append(
                {
                    "object_id": doc["object_id"],
                    "bundle_id": doc["bundle_id"],
                    "section_code": section_code,
                    "entity_kind": entity_kind,
                    "occurrence_count": occurrence_count,
                    "unique_entity_count": unique_count,
                    "typical_occurrences": totals["typical"],
                    "shared_rare_occurrences": totals["shared_rare"],
                    "original_occurrences": totals["original"],
                    "low_population_occurrences": totals["low_population"],
                    "typical_share": round_float(totals["typical"] / occurrence_count if occurrence_count else 0.0),
                    "shared_rare_share": round_float(
                        totals["shared_rare"] / occurrence_count if occurrence_count else 0.0
                    ),
                    "original_share": round_float(totals["original"] / occurrence_count if occurrence_count else 0.0),
                    "low_population_share": round_float(
                        totals["low_population"] / occurrence_count if occurrence_count else 0.0
                    ),
                    "mean_section_idf": round_float(weighted_idf_sum / occurrence_count if occurrence_count else 0.0),
                }
            )
    assessment_rows.sort(key=lambda row: (row["section_code"], row["object_id"], row["entity_kind"]))
    write_csv(
        output_dir / "section_typicality_v0.csv",
        assessment_rows,
        [
            "object_id",
            "bundle_id",
            "section_code",
            "entity_kind",
            "occurrence_count",
            "unique_entity_count",
            "typical_occurrences",
            "shared_rare_occurrences",
            "original_occurrences",
            "low_population_occurrences",
            "typical_share",
            "shared_rare_share",
            "original_share",
            "low_population_share",
            "mean_section_idf",
        ],
    )

    bucket_counts = Counter(row["frequency_bucket"] for row in entity_rows)
    kind_counts = Counter(row["entity_kind"] for row in entity_rows)
    summary = {
        "schema_version": "corpus_frequency_v0",
        "generated_at": generated_at,
        "base_dir": str(base_dir),
        "export_root": str(export_root),
        "output_dir": str(output_dir),
        "document_count": document_count,
        "section_counts": dict(sorted(section_document_counts.items())),
        "entity_kind_counts": dict(sorted(kind_counts.items())),
        "frequency_bucket_counts": dict(sorted(bucket_counts.items())),
        "typical_ratio": typical_ratio,
        "privacy": "hash-only entity library; no raw text in artifacts",
        "files": {
            "section_library": "section_library_v0.csv",
            "entity_frequency": "entity_frequency_v0.csv",
            "section_typicality": "section_typicality_v0.csv",
        },
    }
    write_json(output_dir / "corpus_frequency_v0.json", summary)

    readme = f"""# corpus_frequency_v0

Corpus-frequency library for DocSpectrum typicality/originality analysis.

Generated at:

- `{generated_at}`

Inputs:

- element base: `{base_dir}`
- explorer exports: `{export_root}`

Outputs:

- `section_library_v0.csv`
- `entity_frequency_v0.csv`
- `section_typicality_v0.csv`

Frequency buckets:

- `typical`: entity appears in at least `{typical_ratio:.0%}` of documents with the same section code;
- `shared_rare`: entity appears in more than one same-section document but below the typical threshold;
- `original`: entity appears in one same-section document;
- `low_population`: section has fewer than two documents.

Entity kinds:

- text: `{", ".join(TEXT_ENTITY_KINDS)}`
- structural: `{", ".join(STRUCTURAL_ENTITY_KINDS)}`
- table cell: `{", ".join(TABLE_CELL_ENTITY_KINDS)}`

Artifacts are hash-only: raw text is not written.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=r"E:\output\DocSpectrum\element_base_v0_18_n2",
        help="Directory with generated element_base_v0 artifacts.",
    )
    parser.add_argument(
        "--export-root",
        default=r"E:\output\DocSpectrum\export",
        help="Root directory with explorer exports.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"E:\output\DocSpectrum\corpus_frequency_v0_18_n2",
        help="Directory for corpus-frequency artifacts.",
    )
    parser.add_argument(
        "--typical-ratio",
        type=float,
        default=0.5,
        help="Same-section DF ratio threshold for the typical bucket.",
    )
    args = parser.parse_args()
    build(Path(args.base_dir), Path(args.export_root), Path(args.output_dir), args.typical_ratio)


if __name__ == "__main__":
    main()
