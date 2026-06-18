import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_page_near_match_review_app_v0 import build  # noqa: E402


class PageNearMatchReviewAppTests(unittest.TestCase):
    def test_builds_one_line_compact_csv_and_html_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review = root / "review.csv"
            compact = root / "compact.csv"
            app = root / "review.html"
            row = {
                "review_rank": "1",
                "review_label": "",
                "review_confidence": "",
                "reviewer": "",
                "review_note": "",
                "reviewed_at": "",
                "candidate_id": "candidate-1",
                "candidate_strength": "rare_text_high_overlap",
                "left_object": "left",
                "left_organization": "A",
                "left_file": "left.pdf",
                "left_page": "2",
                "left_pdf_path": "E:/left.pdf",
                "right_object": "right",
                "right_organization": "B",
                "right_file": "right.pdf",
                "right_page": "3",
                "right_pdf_path": "E:/right.pdf",
                "section": "S",
                "structural_similarity": "0.9",
                "text_jaccard": "0.5",
                "shared_text_segments_metric": "2",
                "rare_shared_text_segments": "1",
                "shared_table_layouts": "0",
                "shared_table_content": "0",
                "shared_text_excerpt": "shared long technical phrase\nsecond phrase",
                "left_only_text_excerpt": "left only",
                "right_only_text_excerpt": "right only",
            }
            with review.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)

            build(review, compact, app)

            with compact.open("r", encoding="utf-8-sig", newline="") as handle:
                compact_row = next(csv.DictReader(handle))
            self.assertNotIn("\n", compact_row["кратко_общий_текст"])
            self.assertIn("shared long technical phrase", compact_row["кратко_общий_текст"])
            html_text = app.read_text(encoding="utf-8")
            self.assertIn("candidate-1", html_text)
            self.assertIn("Возможное заимствование", html_text)
            self.assertIn("file:///E:/left.pdf#page=2", html_text)


if __name__ == "__main__":
    unittest.main()
