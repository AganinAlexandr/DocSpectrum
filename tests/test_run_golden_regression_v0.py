from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.run_golden_regression_v0 import extract_value, run


class GoldenRegressionTests(unittest.TestCase):
    def test_extract_value_filters_one_row(self) -> None:
        payload = {"rows": [{"kind": "a", "value": 1}, {"kind": "b", "value": 2}]}
        anchor = {
            "anchor_id": "filtered",
            "filter": {
                "list_path": ["rows"],
                "where": {"kind": "b"},
                "value_path": ["value"],
            },
        }
        self.assertEqual(extract_value(payload, anchor), 2)

    def test_run_supports_equal_approx_between_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            (artifact_root / "sample.json").write_text(
                json.dumps({"exact": 4, "score": 0.9, "rows": [{"name": "x", "value": 0.5}]}),
                encoding="utf-8",
            )
            spec = {
                "anchors": [
                    self._anchor("equal", ["exact"], "equal", expected=4),
                    self._anchor("approx", ["score"], "approx", expected=0.91, tolerance=0.02),
                    {
                        **self._base("between", "between"),
                        "filter": {
                            "list_path": ["rows"],
                            "where": {"name": "x"},
                            "value_path": ["value"],
                        },
                        "minimum": 0.4,
                        "maximum": 0.6,
                    },
                    self._anchor("failed", ["exact"], "equal", expected=5),
                ]
            }
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            summary = run(spec_path, artifact_root, root / "output")
            self.assertEqual((summary["passed_count"], summary["failed_count"]), (3, 1))
            self.assertFalse(summary["all_passed"])

    @staticmethod
    def _base(anchor_id: str, operator: str) -> dict[str, object]:
        return {
            "anchor_id": anchor_id,
            "artifact": "sample.json",
            "operator": operator,
            "validates": "algorithm",
            "meaning": "test",
        }

    @classmethod
    def _anchor(
        cls,
        anchor_id: str,
        path: list[str],
        operator: str,
        **kwargs: object,
    ) -> dict[str, object]:
        return {**cls._base(anchor_id, operator), "json_path": path, **kwargs}


if __name__ == "__main__":
    unittest.main()
