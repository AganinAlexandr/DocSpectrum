import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_page_near_match_calibration_v0 import build  # noqa: E402


def write_queue(path: Path, labels: list[str]) -> None:
    rows = []
    for index, label in enumerate(labels, start=1):
        rows.append(
            {
                "review_rank": str(index),
                "candidate_id": f"candidate-{index}",
                "review_label": label,
                "review_confidence": "high",
                "left_object_id": "a",
                "left_cohort": "A",
                "left_section_code": "S",
                "left_file_name": "a.pdf",
                "left_page_number": "1",
                "right_object_id": "b",
                "right_cohort": "B",
                "right_section_code": "S",
                "right_file_name": "b.pdf",
                "right_page_number": "2",
                "near_match_similarity_v0": "0.9",
                "text_segment_jaccard": "0.5",
                "shared_text_segment_count": "5",
                "rare_shared_text_segment_count": "3",
                "shared_table_layout_count": "1",
                "shared_table_content_count": "0",
                "review_note": "note",
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PageNearMatchCalibrationTests(unittest.TestCase):
    def test_builds_completed_batch_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            write_queue(queue, ["normative_form", "estimate_boilerplate"])
            result = build(queue, root / "output", 2)
            self.assertEqual(result["completed_count"], 2)
            self.assertEqual(result["borrowing_candidate_count"], 0)
            self.assertEqual(result["negative_for_borrowing_count"], 2)

    def test_rejects_pending_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = root / "queue.csv"
            write_queue(queue, ["normative_form", ""])
            with self.assertRaises(ValueError):
                build(queue, root / "output", 2)


if __name__ == "__main__":
    unittest.main()
