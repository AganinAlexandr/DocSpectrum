from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools" / "build_owner_identity_typed_graph_v1.py"
SPEC = importlib.util.spec_from_file_location("owner_identity_typed", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(**overrides: str) -> dict[str, str]:
    result = {
        "handwriting_candidate_v0": "True",
        "four_title_disclosed_object_count": "0",
        "shared_gip_count": "0",
        "temporal_handoff_score": "0",
    }
    result.update(overrides)
    return result


class TypedGraphTests(unittest.TestCase):
    def test_four_title_has_priority(self) -> None:
        edge_type, _ = MODULE.classify_edge(
            row(four_title_disclosed_object_count="3", shared_gip_count="1", temporal_handoff_score="0.8")
        )
        self.assertEqual(edge_type, "disclosed_subcontract_network")

    def test_rename_requires_all_three_signals(self) -> None:
        edge_type, _ = MODULE.classify_edge(
            row(shared_gip_count="1", temporal_handoff_score="0.5")
        )
        self.assertEqual(edge_type, "rename_candidate")

    def test_shared_gip_without_handoff_is_not_rename(self) -> None:
        edge_type, _ = MODULE.classify_edge(
            row(shared_gip_count="1", temporal_handoff_score="0.2")
        )
        self.assertEqual(edge_type, "shared_gip_handwriting")

    def test_handwriting_only_remains_ambiguous(self) -> None:
        edge_type, _ = MODULE.classify_edge(row())
        self.assertEqual(edge_type, "owner_or_template_candidate")


if __name__ == "__main__":
    unittest.main()
