import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_provenance_assessment_v0 import assess_row, build  # noqa: E402


class ProvenanceAssessmentTests(unittest.TestCase):
    def test_third_party_label_blocks_borrowing(self) -> None:
        row = {
            "candidate_id": "a",
            "review_label": "normative_form",
            "review_confidence": "high",
        }
        assessed = assess_row(row)
        self.assertEqual(assessed["authorship_scope"], "third_party")
        self.assertEqual(
            assessed["borrowing_eligibility"],
            "ineligible_third_party",
        )
        self.assertEqual(
            assessed["borrowing_signal_status"],
            "confirmed_non_copy",
        )

    def test_unassessed_never_defaults_to_org_authored(self) -> None:
        assessed = assess_row({"candidate_id": "a", "review_label": ""})
        self.assertEqual(assessed["authorship_scope"], "unknown")
        self.assertEqual(
            assessed["borrowing_eligibility"],
            "blocked_unassessed",
        )

    def test_builds_balanced_stratified_sample(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            rows = []
            for section in ("A", "B"):
                for index in range(12):
                    rows.append(
                        {
                            "candidate_id": f"{section}-{index}",
                            "review_label": "",
                            "review_confidence": "",
                            "review_note": "",
                            "left_section_code": section,
                            "near_match_similarity_v0": str(0.85 + index / 100),
                            "text_segment_jaccard": str(0.2 + index / 40),
                        }
                    )
            with queue.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            result = build(queue, root / "output", per_stratum=1)

            self.assertEqual(result["candidate_count"], 24)
            self.assertEqual(
                result["borrowing_eligibility_counts"],
                {"blocked_unassessed": 24},
            )
            self.assertGreaterEqual(result["stratified_sample_count"], 8)
            self.assertLessEqual(result["stratified_sample_count"], 12)


if __name__ == "__main__":
    unittest.main()
