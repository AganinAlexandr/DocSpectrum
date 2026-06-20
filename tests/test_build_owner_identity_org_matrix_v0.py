from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "build_owner_identity_org_matrix_v0.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("owner_identity", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OwnerIdentityTests(unittest.TestCase):
    def test_canonical_document_prefers_non_auxiliary(self) -> None:
        rows = [
            {"source_file_name": "Раздел АР-УЛ.pdf", "file_size_bytes": "500", "bundle_id": "doc_b"},
            {"source_file_name": "Раздел АР.pdf", "file_size_bytes": "100", "bundle_id": "doc_a"},
        ]
        self.assertEqual(MODULE.canonical_document(rows)["bundle_id"], "doc_a")

    def test_classify_link_keeps_channels_separate(self) -> None:
        self.assertEqual(MODULE.classify_link(0.80, 0.50), "handwriting_transfer_both")
        self.assertEqual(MODULE.classify_link(0.80, 0.10), "handwriting_structure_led")
        self.assertEqual(MODULE.classify_link(0.20, 0.50), "handwriting_content_led")
        self.assertEqual(MODULE.classify_link(0.20, 0.10), "no_transfer_at_v0_thresholds")

    def test_temporal_relation_detects_directional_handoff(self) -> None:
        counts = {
            "old": {"2024-Q1": 5, "2024-Q2": 4},
            "new": {"2024-Q3": 4, "2024-Q4": 5},
        }
        result = MODULE.temporal_relation("old", "new", counts)
        self.assertEqual(result["temporal_handoff_score"], 1.0)
        self.assertEqual(result["temporal_handoff_direction"], "old -> new")

    def test_object_id_from_compound_xlsx_number(self) -> None:
        self.assertEqual(
            MODULE.object_id_from_xlsx({"номер": "100124", "год": "2024"}),
            "1001_24",
        )

    def test_connected_components(self) -> None:
        self.assertEqual(
            MODULE.connected_components([("a", "b"), ("b", "c"), ("x", "y")]),
            [["a", "b", "c"], ["x", "y"]],
        )


if __name__ == "__main__":
    unittest.main()
