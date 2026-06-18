import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_gip_priority_manifest_v0 import MEMBERSHIPS, archive_key  # noqa: E402


class GipPriorityManifestTests(unittest.TestCase):
    def test_manifest_has_expected_unique_objects_and_memberships(self) -> None:
        self.assertEqual(len(MEMBERSHIPS), 56)
        self.assertEqual(
            len({row["source_number"] for row in MEMBERSHIPS}),
            46,
        )

    def test_archive_key(self) -> None:
        self.assertEqual(archive_key("169425"), "1694_25")

    def test_scheme2_reuses_cross_org_roof_objects(self) -> None:
        cross = {
            row["source_number"]
            for row in MEMBERSHIPS
            if row["scheme"] == "scheme_cross_org_fixed_gip_worktype"
        }
        scheme2_roof = {
            row["source_number"]
            for row in MEMBERSHIPS
            if row["scheme"] == "scheme2_fixed_gip_vary_worktype"
            and row["expected_work_type_human"] in {"скатная", "плоская"}
        }
        self.assertEqual(cross, scheme2_roof)


if __name__ == "__main__":
    unittest.main()
