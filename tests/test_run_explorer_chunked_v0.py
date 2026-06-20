import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from run_explorer_chunked_v0 import pending_rows  # noqa: E402


class ExplorerChunkedTests(unittest.TestCase):
    def test_pending_rows_excludes_complete_and_guarded_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = Path(temp_dir)
            complete = export_dir / "doc_complete"
            complete.mkdir()
            for name in (
                "manifest.json",
                "documents.csv",
                "pages.csv",
                "elements.csv",
                "text_segments.csv",
                "tables.csv",
                "table_cells.csv",
            ):
                (complete / name).write_text("", encoding="utf-8")
            rows = [
                {"expected_document_id": "doc_complete"},
                {"expected_document_id": "doc_guarded"},
                {"expected_document_id": "doc_pending"},
            ]

            result = pending_rows(rows, export_dir, {"doc_guarded"})

            self.assertEqual(
                [row["expected_document_id"] for row in result],
                ["doc_pending"],
            )


if __name__ == "__main__":
    unittest.main()
