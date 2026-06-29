#!/usr/bin/env python3
"""Build deterministic one-page PDF fixtures for source-lineage retrieval validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = REPO_ROOT / "schemas" / "source_lineage_fixture_plan_v0.json"
DEFAULT_OUTPUT = Path(r"E:\output\DocSpectrum\source_lineage_fixtures_v0")
TEXT_VARIANTS = ("exact", "format_only", "numeric_edit", "sentence_reorder", "partial_25", "partial_50")
TABLE_VARIANTS = (
    "exact", "format_only", "values_edit", "row_reorder", "row_drop_25", "column_change",
    "form_same_content_new",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_plan(plan: dict[str, Any]) -> None:
    families = plan["text_families"] + plan["table_families"]
    ids = [family["family_id"] for family in families]
    if len(ids) != 16 or len(set(ids)) != 16:
        raise ValueError("Fixture plan must contain 16 unique lineage families")
    splits = [family["split"] for family in families]
    if splits.count("calibration") != 10 or splits.count("evaluation") != 6:
        raise ValueError("Fixture plan must contain 10 calibration and 6 evaluation families")
    for family in plan["text_families"]:
        if len(family["sentences"]) < 4:
            raise ValueError(f"Text family {family['family_id']} needs at least four sentences")
    for family in plan["table_families"]:
        if len(family["headers"]) != 4 or len(family["rows"]) < 8:
            raise ValueError(f"Table family {family['family_id']} needs four columns and eight rows")
        if any(len(row) != len(family["headers"]) for row in family["rows"]):
            raise ValueError(f"Table family {family['family_id']} has a ragged row")


def edit_numbers(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if "." in value:
            return f"{float(value) + 0.7:.2f}".rstrip("0").rstrip(".")
        return str(int(value) + 3)

    return re.sub(r"(?<![A-Za-zА-Яа-я])\d+(?:\.\d+)?", replace, text)


def transform_text(sentences: list[str], variant: str) -> list[str]:
    if variant in {"exact", "format_only"}:
        return list(sentences)
    if variant == "numeric_edit":
        return [edit_numbers(sentence) for sentence in sentences]
    if variant == "sentence_reorder":
        return list(reversed(sentences))
    if variant == "partial_25":
        return [sentence for index, sentence in enumerate(sentences) if index % 4 != 3]
    if variant == "partial_50":
        return [sentence for index, sentence in enumerate(sentences) if index % 2 == 0]
    raise ValueError(f"Unsupported text variant: {variant}")


def replacement_cell(row_index: int, column_index: int) -> str:
    values = ("Комплект", "Узел", "Материал", "Элемент", "Изделие", "Прибор", "Деталь", "Модуль")
    return f"{values[row_index % len(values)]} {column_index + 1}-{row_index + 1}"


def transform_table(headers: list[str], rows: list[list[str]], variant: str) -> tuple[list[str], list[list[str]]]:
    result_headers = list(headers)
    result_rows = deepcopy(rows)
    if variant in {"exact", "format_only"}:
        return result_headers, result_rows
    if variant == "values_edit":
        return result_headers, [[row[0], *[edit_numbers(cell) for cell in row[1:]]] for row in result_rows]
    if variant == "row_reorder":
        return result_headers, list(reversed(result_rows))
    if variant == "row_drop_25":
        return result_headers, [row for index, row in enumerate(result_rows) if index % 4 != 3]
    if variant == "column_change":
        return [*result_headers, "Примечание"], [
            [*row, f"Вариант {index + 1}"] for index, row in enumerate(result_rows)
        ]
    if variant == "form_same_content_new":
        return result_headers, [
            [replacement_cell(row_index, column_index) for column_index in range(len(result_headers))]
            for row_index in range(len(result_rows))
        ]
    raise ValueError(f"Unsupported table variant: {variant}")


def fixture_specs(plan: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for kind, families, variants in (
        ("text", plan["text_families"], TEXT_VARIANTS),
        ("table", plan["table_families"], TABLE_VARIANTS),
    ):
        for family in families:
            specs.append({"kind": kind, "role": "source", "variant_id": "canonical", **family})
            for variant in variants:
                specs.append({"kind": kind, "role": "query", "variant_id": variant, **family})
    ids = [f"{spec['family_id']}__{spec['role']}__{spec['variant_id']}" for spec in specs]
    if len(ids) != 120 or len(set(ids)) != 120:
        raise AssertionError("Expected 120 unique source/query fixtures")
    return specs


def content_for(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["kind"] == "text":
        variant = "exact" if spec["role"] == "source" else spec["variant_id"]
        return {"sentences": transform_text(spec["sentences"], variant)}
    variant = "exact" if spec["role"] == "source" else spec["variant_id"]
    headers, rows = transform_table(spec["headers"], spec["rows"], variant)
    return {"headers": headers, "rows": rows}


def render_pdf(
    path: Path,
    kind: str,
    content: dict[str, Any],
    font_file: Path,
    format_only: bool,
    instance_token: str,
) -> None:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required; use the PDF Structure Explorer Python environment") from exc

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_font(fontname="fixture", fontfile=str(font_file))
    page.draw_rect(page.rect, color=(0.75, 0.75, 0.75), width=0.5)
    title = "Техническое описание" if kind == "text" else "Таблица технических данных"
    title_size = 13 if not format_only else 12
    page.insert_textbox(
        fitz.Rect(54, 42, 541, 82), title, fontname="fixture", fontsize=title_size,
        align=fitz.TEXT_ALIGN_CENTER,
    )

    if kind == "text":
        body = "\n\n".join(content["sentences"])
        body_rect = fitz.Rect(64 if format_only else 54, 105, 531 if format_only else 541, 790)
        remainder = page.insert_textbox(
            body_rect,
            body,
            fontname="fixture",
            fontsize=10.2 if format_only else 11,
            lineheight=1.45 if format_only else 1.25,
            align=fitz.TEXT_ALIGN_JUSTIFY,
        )
        if remainder < 0:
            raise ValueError(f"Text fixture overflow: {path.name}")
    else:
        headers = content["headers"]
        rows = content["rows"]
        left, right, top = 44.0, 551.0, 115.0
        row_height = 48.0 if format_only else 45.0
        column_width = (right - left) / len(headers)
        all_rows = [headers, *rows]
        for row_index, row in enumerate(all_rows):
            y0 = top + row_index * row_height
            y1 = y0 + row_height
            for column_index, cell in enumerate(row):
                x0 = left + column_index * column_width
                x1 = x0 + column_width
                fill = (0.93, 0.93, 0.93) if row_index == 0 else None
                page.draw_rect(
                    fitz.Rect(x0, y0, x1, y1), color=(0.25, 0.25, 0.25),
                    fill=fill, width=0.8 if format_only else 0.5,
                )
                remainder = page.insert_textbox(
                    fitz.Rect(x0 + 4, y0 + 5, x1 - 4, y1 - 4),
                    str(cell),
                    fontname="fixture",
                    fontsize=8.4 if format_only else 8.8,
                    align=fitz.TEXT_ALIGN_CENTER,
                )
                if remainder < 0:
                    raise ValueError(f"Table cell overflow in {path.name}: {cell!r}")

    document.set_metadata(
        {
            "title": "DocSpectrum source-lineage fixture",
            "author": "DocSpectrum validation",
            "subject": "Synthetic retrieval fixture",
            "keywords": f"source-lineage instance-{instance_token}",
            "creator": "build_source_lineage_fixtures_v0",
            "producer": "PyMuPDF",
            "creationDate": "D:20000101000000+00'00'",
            "modDate": "D:20000101000000+00'00'",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path, garbage=4, deflate=True, no_new_id=True)
    document.close()


def build(plan_path: Path, output_dir: Path, font_file: Path) -> dict[str, Any]:
    plan = load_plan(plan_path)
    validate_plan(plan)
    font_hash = sha256_file(font_file)
    manifest_rows: list[dict[str, Any]] = []
    for spec in fixture_specs(plan):
        fixture_id = f"{spec['family_id']}__{spec['role']}__{spec['variant_id']}"
        instance_token = sha256_bytes(fixture_id.encode("utf-8"))[:16]
        relative_path = Path("pdf") / spec["role"] / f"{fixture_id}.pdf"
        content = content_for(spec)
        render_pdf(
            output_dir / relative_path,
            spec["kind"],
            content,
            font_file,
            format_only=spec["role"] == "query" and spec["variant_id"] == "format_only",
            instance_token=instance_token,
        )
        manifest_rows.append(
            {
                "fixture_id": fixture_id,
                "family_id": spec["family_id"],
                "component_kind": spec["kind"],
                "split": spec["split"],
                "role": spec["role"],
                "variant_id": spec["variant_id"],
                "expected_family_id": spec["family_id"],
                "relative_pdf_path": str(relative_path),
                "content_sha256": sha256_bytes(canonical_json(content)),
                "pdf_sha256": sha256_file(output_dir / relative_path),
                "font_sha256": font_hash,
                "instance_token": instance_token,
                "page_count": 1,
                "ground_truth": "lineage_by_construction_before_extraction",
            }
        )

    fields = list(manifest_rows[0])
    with (output_dir / "lineage_manifest_v0.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)
    (output_dir / "fixture_plan_snapshot_v0.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "schema_version": "source_lineage_fixtures_v0",
        "plan_sha256": sha256_file(plan_path),
        "font_file": str(font_file),
        "font_sha256": font_hash,
        "fixture_count": len(manifest_rows),
        "source_count": sum(row["role"] == "source" for row in manifest_rows),
        "query_count": sum(row["role"] == "query" for row in manifest_rows),
        "text_count": sum(row["component_kind"] == "text" for row in manifest_rows),
        "table_count": sum(row["component_kind"] == "table" for row in manifest_rows),
        "calibration_family_count": 10,
        "evaluation_family_count": 6,
        "exact_query_byte_distinct_count": sum(
            1
            for row in manifest_rows
            if row["role"] == "query"
            and row["variant_id"] == "exact"
            and row["pdf_sha256"]
            != next(
                source["pdf_sha256"]
                for source in manifest_rows
                if source["role"] == "source" and source["family_id"] == row["family_id"]
            )
        ),
        "privacy": "synthetic fixture content; manifest stores hashes and lineage metadata",
        "claim_boundary": "component lineage ground truth; not borrowing or authorship ground truth",
        "files": {"manifest": "lineage_manifest_v0.csv", "plan": "fixture_plan_snapshot_v0.json"},
    }
    (output_dir / "source_lineage_fixtures_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--assert-reference", action="store_true")
    args = parser.parse_args()
    summary = build(args.plan, args.output_dir, args.font_file)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.assert_reference:
        expected = {
            "fixture_count": 120,
            "source_count": 16,
            "query_count": 104,
            "text_count": 56,
            "table_count": 64,
            "exact_query_byte_distinct_count": 16,
        }
        mismatches = {key: (summary[key], value) for key, value in expected.items() if summary[key] != value}
        if mismatches:
            raise SystemExit(f"Fixture reference mismatch: {mismatches}")


if __name__ == "__main__":
    main()
