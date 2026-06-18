import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from run_explorer_gip_batch_v0 import is_complete_export  # noqa: E402


class ExplorerGipBatchTests(unittest.TestCase):
    def test_complete_export_requires_core_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            doc = root / "doc_a"
            doc.mkdir()
            for name in (
                "manifest.json",
                "documents.csv",
                "pages.csv",
                "elements.csv",
                "text_segments.csv",
                "tables.csv",
                "table_cells.csv",
            ):
                (doc / name).write_text("", encoding="utf-8")
            self.assertTrue(is_complete_export(root, "doc_a"))
            (doc / "tables.csv").unlink()
            self.assertFalse(is_complete_export(root, "doc_a"))


if __name__ == "__main__":
    unittest.main()
