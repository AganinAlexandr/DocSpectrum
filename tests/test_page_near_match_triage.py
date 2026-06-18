import csv
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_page_near_match_triage_v0 import build, load_labels  # noqa: E402


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class PageNearMatchTriageTests(unittest.TestCase):
    def test_build_preserves_existing_human_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates = root / "candidates.csv"
            documents = root / "documents_index.csv"
            export_root = root / "exports"
            labels = root / "labels.csv"
            output_dir = root / "output"

            write_csv(
                candidates,
                [
                    {
                        "candidate_id": "candidate-1",
                        "candidate_strength": "rare_text_high_overlap",
                        "left_crc32": "aaaaaaaa",
                        "left_page_number": "2",
                        "right_crc32": "bbbbbbbb",
                        "right_page_number": "3",
                        "query_bundle_id": "doc_aaaaaaaa",
                        "query_cohort": "A",
                        "neighbor_bundle_id": "doc_bbbbbbbb",
                        "neighbor_cohort": "B",
                        "section_relation": "same_section",
                        "near_match_similarity_v0": "0.9",
                        "text_segment_jaccard": "0.6",
                        "shared_text_segment_count": "4",
                        "rare_shared_text_segment_count": "2",
                        "shared_text_global_idf_sum": "5.0",
                        "max_shared_text_global_idf": "3.0",
                        "table_layout_jaccard": "0.0",
                        "shared_table_layout_count": "0",
                        "table_content_jaccard": "0.0",
                        "shared_table_content_count": "0",
                        "interpretation_note": "research_only",
                    }
                ],
            )
            write_csv(
                documents,
                [
                    {
                        "object_id": "object-a",
                        "bundle_id": "doc_aaaaaaaa",
                        "section_code": "S",
                        "crc32": "AAAAAAAA",
                        "file_name": "a.pdf",
                        "page_count": "10",
                    },
                    {
                        "object_id": "object-b",
                        "bundle_id": "doc_bbbbbbbb",
                        "section_code": "S",
                        "crc32": "BBBBBBBB",
                        "file_name": "b.pdf",
                        "page_count": "12",
                    },
                ],
            )
            for object_id, bundle_id, pdf_name in (
                ("object-a", "doc_aaaaaaaa", "a.pdf"),
                ("object-b", "doc_bbbbbbbb", "b.pdf"),
            ):
                write_csv(
                    export_root / object_id / bundle_id / "documents.csv",
                    [
                        {
                            "file_path": str(root / pdf_name),
                            "parse_status": "parsed",
                        }
                    ],
                )
            write_csv(
                labels,
                [
                    {
                        "candidate_id": "candidate-1",
                        "review_label": "normative_form",
                        "review_confidence": "high",
                        "reviewer": "human",
                        "review_note": "standard form",
                        "reviewed_at": "2026-06-18",
                    }
                ],
            )

            summary = build(
                candidates,
                documents,
                export_root,
                output_dir,
                labels,
            )

            self.assertEqual(summary["label_counts"], {"normative_form": 1})
            preserved = load_labels(labels)["candidate-1"]
            self.assertEqual(preserved["review_label"], "normative_form")
            self.assertEqual(preserved["review_note"], "standard form")

    def test_load_labels_rejects_unknown_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            labels = Path(temp_dir) / "labels.csv"
            write_csv(
                labels,
                [
                    {
                        "candidate_id": "candidate-1",
                        "review_label": "not_in_dictionary",
                        "review_confidence": "high",
                        "reviewer": "",
                        "review_note": "",
                        "reviewed_at": "",
                    }
                ],
            )
            with self.assertRaises(ValueError):
                load_labels(labels)


if __name__ == "__main__":
    unittest.main()
