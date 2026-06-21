from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_remark_depth_calibration_v1 import (  # noqa: E402
    normalize_label_text,
    predicted_level,
    role_key,
)
from remark_features import classify_depth, classify_remark  # noqa: E402


def test_norm_reference_alone_does_not_make_substantial() -> None:
    text = "Уточнить номер листа согласно СП 20.13330."
    categories, _ = classify_remark(text)
    depth, reasons = classify_depth(text, categories)
    assert depth == "simple_candidate"
    assert "normative_reference" not in reasons


def test_long_engineering_remark_can_be_substantial() -> None:
    text = (
        "На чертеже необходимо исправить конструктивный узел и согласовать его "
        "с расчетной схемой, указать все размеры, материалы и сопряжения элементов."
    )
    categories, _ = classify_remark(text)
    depth, _ = classify_depth(text, categories)
    assert depth == "substantial_candidate"


def test_predicted_level_is_binary_current_scale() -> None:
    assert predicted_level("substantial_candidate") == 2
    assert predicted_level("simple_candidate") == 1
    assert predicted_level("review_needed") == 1


def test_role_mapping() -> None:
    assert role_key("ceiling(1)") == "class_1"
    assert role_key("floor(3)") == "floor_3"
    assert role_key("holdout") == "holdout"


def test_excel_line_marker_is_removed() -> None:
    assert normalize_label_text("a_x000D_ b") == "a  b"
