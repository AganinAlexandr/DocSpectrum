from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_gip_control_h2_alias_canon_v0 import (  # noqa: E402
    build_cell_rows,
    build_gip_summary_rows,
)


def pair(relation: str, left_org: str, right_org: str, shingle: float) -> dict[str, str]:
    return {
        "cell_id": "h2|сергеев|скатная|КР",
        "left_gip": "сергеев",
        "work_type_key": "скатная",
        "section_code": "КР",
        "relation": relation,
        "left_org": left_org,
        "right_org": right_org,
        "style_composition_similarity_v0": "0.8",
        "page_near_similarity_mean_v0_2": "0.7",
        "residual_page_near_shingle_mean_v0_3": str(shingle),
        "residual_page_near_strong_share_v0_3": "0.2",
    }


def test_build_cell_rows_requires_both_relations_for_matched_status() -> None:
    rows = build_cell_rows(
        [
            pair("same_org", "Ватага", "Ватага", 0.2),
            pair("cross_org", "Ватага", "СП Стройинвест ГРУПП", 0.1),
        ]
    )

    assert rows[0]["comparison_status"] == "matched_same_and_cross"
    assert rows[0]["same_org_pair_count"] == 1
    assert rows[0]["cross_org_pair_count"] == 1
    assert rows[0]["cross_minus_same_residual_shingle"] == -0.1


def test_build_cell_rows_marks_cross_only_as_data_gap() -> None:
    rows = build_cell_rows(
        [pair("cross_org", "ООО Стройразвитие", "Стройразвитие М", 0.3)]
    )

    assert rows[0]["comparison_status"] == "cross_only_no_same_org_baseline"
    assert rows[0]["same_org_pair_count"] == 0
    assert rows[0]["cross_org_pair_count"] == 1


def test_build_gip_summary_uses_equal_cell_weight() -> None:
    cells = build_cell_rows(
        [
            pair("same_org", "Ватага", "Ватага", 0.2),
            pair("cross_org", "Ватага", "СП Стройинвест ГРУПП", 0.1),
        ]
    )

    summary = build_gip_summary_rows(cells)[0]

    assert summary["gip"] == "сергеев"
    assert summary["matched_cell_count"] == 1
    assert summary["cross_minus_same_residual_shingle_cell_median"] == -0.1
