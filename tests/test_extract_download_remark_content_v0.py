from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from extract_download_remark_content_v0 import (  # noqa: E402
    choose_file,
    is_remark_header,
    normalize_object_id,
    round_from_filename,
    section_from_filename,
)


def test_filename_parsing_uses_token_boundaries() -> None:
    assert section_from_filename("1190-24 , зам. КР, ул. Советская.doc") == "КР"
    assert section_from_filename("1190-24 , зам. ПОКР, ул. Советская.doc") == "ПОС"
    assert section_from_filename("1190-24 , зам. АР, ул. Советская.doc") == ""


def test_round_parsing() -> None:
    assert round_from_filename("1222-24 , зам_4 ПОС.doc") == 4
    assert round_from_filename("1222-24 , зам. ПОС.doc") == 1


def test_choose_file_prefers_first_round_and_non_accepted() -> None:
    rows = [
        {"path": Path("x зам_2 ПОС.doc"), "round": 2},
        {"path": Path("x зам. ПОС, ПРИНЯТО.doc"), "round": 1},
        {"path": Path("x зам. ПОС.doc"), "round": 1},
    ]
    assert choose_file(rows)["path"].name == "x зам. ПОС.doc"


def test_object_id_is_padded() -> None:
    assert normalize_object_id("292", "24") == "0292_24"


def test_supported_header_families() -> None:
    assert is_remark_header("Содержание замечания")
    assert is_remark_header("Замечания экспертизы")
    assert is_remark_header("Текст замечаний")
