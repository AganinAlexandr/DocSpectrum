from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.build_source_lineage_fixtures_v0 import (
    DEFAULT_PLAN,
    build,
    content_for,
    fixture_specs,
    load_plan,
    transform_table,
    transform_text,
    validate_plan,
)


def available_font() -> Path | None:
    candidates = [
        os.environ.get("DOCSPECTRUM_TEST_FONT", ""),
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    return next((Path(value) for value in candidates if value and Path(value).is_file()), None)


class SourceLineageFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_plan(DEFAULT_PLAN)

    def test_plan_and_fixture_reference_counts(self) -> None:
        validate_plan(self.plan)
        specs = fixture_specs(self.plan)
        self.assertEqual(len(specs), 120)
        self.assertEqual(sum(spec["role"] == "source" for spec in specs), 16)
        self.assertEqual(sum(spec["role"] == "query" for spec in specs), 104)
        self.assertEqual(sum(spec["split"] == "calibration" for spec in specs if spec["role"] == "source"), 10)
        self.assertEqual(sum(spec["split"] == "evaluation" for spec in specs if spec["role"] == "source"), 6)

    def test_text_transformations_are_deterministic_and_distinct(self) -> None:
        sentences = self.plan["text_families"][0]["sentences"]
        self.assertEqual(transform_text(sentences, "exact"), sentences)
        self.assertEqual(transform_text(sentences, "format_only"), sentences)
        self.assertEqual(transform_text(sentences, "sentence_reorder"), list(reversed(sentences)))
        self.assertEqual(len(transform_text(sentences, "partial_25")), 3)
        self.assertEqual(len(transform_text(sentences, "partial_50")), 2)
        self.assertNotEqual(transform_text(sentences, "numeric_edit"), sentences)

    def test_table_transformations_separate_form_and_content(self) -> None:
        family = self.plan["table_families"][0]
        headers, rows = family["headers"], family["rows"]
        same_headers, new_content = transform_table(headers, rows, "form_same_content_new")
        self.assertEqual(same_headers, headers)
        self.assertEqual((len(new_content), len(new_content[0])), (len(rows), len(headers)))
        self.assertNotEqual(new_content, rows)
        changed_headers, changed_columns = transform_table(headers, rows, "column_change")
        self.assertEqual(len(changed_headers), len(headers) + 1)
        self.assertTrue(all(len(row) == len(changed_headers) for row in changed_columns))

    def test_ground_truth_is_family_lineage_not_variant_content(self) -> None:
        specs = fixture_specs(self.plan)
        for spec in specs:
            content = content_for(spec)
            self.assertTrue(content)
            self.assertNotIn("expected_family_id", content)
            self.assertNotIn(spec["family_id"], json.dumps(content, ensure_ascii=False))

    @unittest.skipUnless(available_font(), "No Cyrillic test font is available")
    def test_build_is_byte_deterministic_and_exact_queries_are_distinct_files(self) -> None:
        try:
            import fitz  # type: ignore
        except ImportError:
            self.skipTest("PyMuPDF is unavailable")
        font = available_font()
        assert font is not None
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            summary = build(DEFAULT_PLAN, first, font)
            build(DEFAULT_PLAN, second, font)
            self.assertEqual(summary["fixture_count"], 120)
            self.assertEqual(summary["exact_query_byte_distinct_count"], 16)
            with (first / "lineage_manifest_v0.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                first_rows = list(csv.DictReader(handle))
            with (second / "lineage_manifest_v0.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                second_rows = list(csv.DictReader(handle))
            first_hashes = [(row["fixture_id"], row["content_sha256"], row["pdf_sha256"]) for row in first_rows]
            second_hashes = [(row["fixture_id"], row["content_sha256"], row["pdf_sha256"]) for row in second_rows]
            self.assertEqual(first_hashes, second_hashes)
            sample = next(first.rglob("text_*__query__exact.pdf"))
            with fitz.open(sample) as document:
                extracted = document[0].get_text()
            self.assertIn("Техническое", extracted)
            self.assertNotIn("text_", extracted)


if __name__ == "__main__":
    unittest.main()
