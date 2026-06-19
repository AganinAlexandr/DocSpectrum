from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_gip_control_registry_v0 import (  # noqa: E402
    build_h1_cells,
    build_h2_cells,
    normalize_work_type,
    organization_identity_keys,
    resolve_organization_name,
    summarize_object_row,
)
from build_gip_control_baseline_v0 import summarize_metrics  # noqa: E402
from build_gip_control_baseline_v0 import include_section  # noqa: E402


def test_normalize_work_type_strips_wrappers() -> None:
    assert normalize_work_type("_плоская_") == "плоская"
    assert normalize_work_type("скатная\\") == "скатная"
    assert normalize_work_type("Подвал, дренаж") == "подвал дренаж"


def test_summarize_object_row_prefers_subcontractor_effective_author() -> None:
    manifest_row = {
        "object_id": "1500_25",
        "group": "скатная",
        "gip": "локтев",
        "org": "ватага",
    }
    document_row = {
        "section_code": "КР",
        "crc32": "ABCD1234",
        "expected_document_id": "doc_abcd1234",
        "title_page_count": "4",
        "title_structure_status": "lead_and_subcontractor_expected",
        "party_group_count": "2",
    }
    parties = [
        {
            "role": "lead_designer",
            "organization_name_normalized": "ооо «ватага»",
            "organization_name_raw": "ООО «ВАТАГА»",
            "gip_surname_normalized": "сергеев",
            "effective_author": "False",
            "effective_author_rule": "lead_contractual_not_effective_author",
            "manual_review_required": "False",
        },
        {
            "role": "subcontractor",
            "organization_name_normalized": "ооо «сп стройинвест групп»",
            "organization_name_raw": "ООО «СП Стройинвест ГРУПП»",
            "gip_surname_normalized": "локтев",
            "effective_author": "True",
            "effective_author_rule": "subcontractor_actual_author",
            "manual_review_required": "False",
        },
    ]
    alias = {
        "ооо ватага": "Ватага",
        "ооо сп стройинвест групп": "СП Стройинвест ГРУПП",
    }

    row = summarize_object_row(manifest_row, document_row, parties, alias)

    assert row["effective_gip"] == "локтев"
    assert row["effective_org_canonical"] == "СП Стройинвест ГРУПП"
    assert row["lead_org_canonical"] == "Ватага"
    assert row["subcontractor_org_canonical"] == "СП Стройинвест ГРУПП"
    assert row["authorship_status"] == "ready"


def test_resolve_organization_name_uses_legal_form_independent_identity() -> None:
    alias = {
        "ватага": "Ватага",
        "инфрастройинтекс": "ИнфраСтройИнтекс",
        "сп стройинвест групп": "СП Стройинвест ГРУПП",
    }

    assert organization_identity_keys('ООО «Ватага»') == ("ооо ватага", "ватага")
    assert resolve_organization_name(
        {"organization_name_normalized": 'ооо «ватага»'},
        alias,
    ) == ("Ватага", "alias_registry")
    assert resolve_organization_name(
        {"organization_name_normalized": 'ООО «ИнфраСтройИнтекс»'},
        alias,
    ) == ("ИнфраСтройИнтекс", "alias_registry")
    assert resolve_organization_name(
        {"organization_name_normalized": 'ООО «СП Стройинвест ГРУПП»'},
        alias,
    ) == ("СП Стройинвест ГРУПП", "alias_registry")

    development_alias = {
        "ооо стройразвитие": "ООО Стройразвитие",
        "стройразвитие": "Стройразвитие М",
        "стройразвитие м": "Стройразвитие М",
    }
    assert resolve_organization_name(
        {"organization_name_normalized": 'ООО «Стройразвитие»'},
        development_alias,
    ) == ("ООО Стройразвитие", "alias_registry")
    assert resolve_organization_name(
        {"organization_name_normalized": 'ООО «Стройразвитие М»'},
        development_alias,
    ) == ("Стройразвитие М", "alias_registry")


def test_cell_builders_detect_h1_and_h2_eligibility() -> None:
    section_rows = [
        {
            "object_id": "o1",
            "section_code": "КР",
            "work_type_key": "скатная",
            "effective_gip": "локтев",
            "effective_org_canonical": "СтройМонтаж СП",
        },
        {
            "object_id": "o2",
            "section_code": "КР",
            "work_type_key": "скатная",
            "effective_gip": "ефимов",
            "effective_org_canonical": "СтройМонтаж СП",
        },
        {
            "object_id": "o3",
            "section_code": "КР",
            "work_type_key": "скатная",
            "effective_gip": "ефимов",
            "effective_org_canonical": "СтройМонтаж СП",
        },
        {
            "object_id": "o4",
            "section_code": "КР",
            "work_type_key": "скатная",
            "effective_gip": "сергеев",
            "effective_org_canonical": "Ватага",
        },
        {
            "object_id": "o5",
            "section_code": "КР",
            "work_type_key": "скатная",
            "effective_gip": "сергеев",
            "effective_org_canonical": "СП Стройинвест ГРУПП",
        },
    ]

    h1_rows = build_h1_cells(section_rows)
    h2_rows = build_h2_cells(section_rows)

    h1 = next(
        row
        for row in h1_rows
        if row["org_canonical"] == "СтройМонтаж СП"
        and row["work_type_key"] == "скатная"
        and row["section_code"] == "КР"
    )
    h2 = next(
        row
        for row in h2_rows
        if row["gip"] == "сергеев"
        and row["work_type_key"] == "скатная"
        and row["section_code"] == "КР"
    )

    assert h1["eligible_for_gip_control"] is True
    assert h2["eligible_for_gip_control"] is True


def test_summarize_metrics_exposes_v0_1_headlines() -> None:
    rows = [
        {
            "style_similarity_v0": 0.60,
            "style_ratio_similarity_v0": 0.40,
            "style_composition_similarity_v0": 0.80,
            "content_similarity_v0": 0.10,
            "text_segment_jaccard": 0.05,
            "text_word_shingle_jaccard": 0.20,
        },
        {
            "style_similarity_v0": 0.80,
            "style_ratio_similarity_v0": 0.60,
            "style_composition_similarity_v0": 0.90,
            "content_similarity_v0": 0.20,
            "text_segment_jaccard": 0.10,
            "text_word_shingle_jaccard": 0.30,
        },
    ]

    metrics = summarize_metrics(rows)

    assert metrics["style_similarity_median_v0"] == 0.7
    assert metrics["style_ratio_similarity_median_v0"] == 0.5
    assert metrics["style_composition_similarity_median_v0"] == 0.85
    assert metrics["content_similarity_median_v0"] == 0.15
    assert metrics["text_word_shingle_jaccard_median_v0"] == 0.25


def test_include_section_excludes_pz_and_unknown() -> None:
    excluded = {"UNKNOWN", "ПЗ"}

    assert include_section("КР", excluded) is True
    assert include_section("ПОС", excluded) is True
    assert include_section("ПЗ", excluded) is False
    assert include_section("UNKNOWN", excluded) is False
