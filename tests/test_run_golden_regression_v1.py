from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.run_golden_regression_v1 import evaluate, extract_value, main, run


class GoldenRegressionV1Tests(unittest.TestCase):
    def test_extract_value_requires_one_filtered_row(self) -> None:
        anchor = {
            "anchor_id": "filtered",
            "filter": {"list_path": ["rows"], "where": {"kind": "b"}, "value_path": ["value"]},
        }
        self.assertEqual(extract_value({"rows": [{"kind": "b", "value": 2}]}, anchor), 2)
        with self.assertRaisesRegex(ValueError, "found 0"):
            extract_value({"rows": [],}, anchor)
        with self.assertRaisesRegex(ValueError, "found 2"):
            extract_value({"rows": [{"kind": "b", "value": 1}, {"kind": "b", "value": 2}]}, anchor)

    def test_extract_value_supports_named_operands(self) -> None:
        anchor = {
            "anchor_id": "relation",
            "operands": [
                {"name": "left", "json_path": ["a"]},
                {"name": "right", "json_path": ["b"]},
            ],
        }
        self.assertEqual(extract_value({"a": 3, "b": 1}, anchor), {"left": 3, "right": 1})

    def test_equal_is_type_strict(self) -> None:
        self.assertEqual(evaluate(0, {"operator": "equal", "expected": 0})[0], True)
        self.assertEqual(evaluate(False, {"operator": "equal", "expected": 0})[0], False)
        self.assertEqual(evaluate(1.0, {"operator": "equal", "expected": 1})[0], False)

    def test_numeric_operators_reject_bool_and_strings(self) -> None:
        for actual in (True, "0.9"):
            with self.assertRaises(TypeError):
                evaluate(actual, {"operator": "approx", "expected": 0.9, "tolerance": 0.1})
            with self.assertRaises(TypeError):
                evaluate(actual, {"operator": "between", "minimum": 0.8, "maximum": 1.0})

    def test_relational_operators(self) -> None:
        summed = evaluate({"body": 5344, "title": 137}, {"operator": "sum_equal", "expected": 5481})
        separated = evaluate(
            {"same": 0.3559, "different": 0.0394},
            {
                "operator": "difference_at_least",
                "left_operand": "same",
                "right_operand": "different",
                "minimum_difference": 0.25,
            },
        )
        self.assertTrue(summed[0])
        self.assertTrue(separated[0])

    def test_unsupported_operator_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported operator"):
            evaluate(1, {"operator": "unknown"})

    def test_run_fails_closed_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            (artifact_root / "good.json").write_text(json.dumps({"value": 4}), encoding="utf-8")
            (artifact_root / "bad.json").write_text("{not-json", encoding="utf-8")
            spec = {
                "anchors": [
                    self._anchor("passed", "good.json", ["value"], "equal", expected=4),
                    self._anchor("missing", "missing.json", ["value"], "equal", expected=4),
                    self._anchor("malformed", "bad.json", ["value"], "equal", expected=4),
                    self._anchor("missing_path", "good.json", ["absent"], "equal", expected=4),
                    self._anchor("unsupported", "good.json", ["value"], "unknown"),
                ]
            }
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            output_dir = root / "output"
            summary = run(spec_path, artifact_root, output_dir)
            self.assertEqual((summary["passed_count"], summary["failed_count"]), (1, 4))
            self.assertFalse(summary["all_passed"])
            self.assertTrue((output_dir / "golden_regression_v1.json").exists())
            with (output_dir / "golden_regression_results_v1.csv").open(
                "r", encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(row["status"] == "failed" for row in rows[1:]))

    def test_assert_reference_returns_nonzero_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            (artifact_root / "sample.json").write_text(json.dumps({"value": 1}), encoding="utf-8")
            spec_path = root / "spec.json"
            spec_path.write_text(
                json.dumps({"anchors": [self._anchor("fail", "sample.json", ["value"], "equal", expected=2)]}),
                encoding="utf-8",
            )
            exit_code = main(
                [
                    "--spec", str(spec_path),
                    "--artifact-root", str(artifact_root),
                    "--output-dir", str(root / "output"),
                    "--assert-reference",
                ]
            )
            self.assertEqual(exit_code, 1)

    @staticmethod
    def _anchor(
        anchor_id: str,
        artifact: str,
        path: list[str],
        operator: str,
        **kwargs: object,
    ) -> dict[str, object]:
        return {
            "anchor_id": anchor_id,
            "artifact": artifact,
            "json_path": path,
            "operator": operator,
            "validates": "algorithm",
            "meaning": "test",
            "stability_mode": "test",
            **kwargs,
        }


if __name__ == "__main__":
    unittest.main()
