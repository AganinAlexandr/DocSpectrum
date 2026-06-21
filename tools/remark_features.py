"""Shared privacy-safe remark normalization, typing, and depth heuristics."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from text_features import normalize_text


CATEGORY_RULES = (
    ("thermal_engineering", r"теплотех|теплопередач|сопротивлен.{0,20}тепл|утеплител"),
    ("technical_economic_indicators", r"\bтэп\b|технико-экономическ"),
    ("graphics", r"на план|на чертеж|черт[её]ж|узел|разрез|схем|графическ"),
    ("regulatory", r"\bсп\s*\d|\bгост\b|\bфз\b|постановлен|норматив|пп\s*87"),
    ("project_composition", r"\bиул\b|\bирд\b|состав.{0,15}пд|исходно-разрешительн|отсутству.{0,20}раздел"),
    ("mismatch", r"не соответств|несоответ|не совпада|противореч|неверн|ошибоч"),
    ("work_organization", r"календарн.{0,15}план|стройгенплан|охрана труда|захватк"),
    ("formatting", r"оформ|нумерац|штамп|рамк|подпис|завер"),
    ("clarification", r"указать|уточнить|пояснить|обосновать|почему|для чего"),
    ("correction", r"скоррект|исправ|устран|заменить|изменить|дополнить"),
)

ENGINEERING_CATEGORIES = {
    "thermal_engineering",
    "technical_economic_indicators",
    "graphics",
    "regulatory",
    "project_composition",
    "mismatch",
    "work_organization",
}


def remark_hash(value: str) -> str:
    normalized = normalize_text(value)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def classify_remark(value: str) -> tuple[list[str], str]:
    normalized = normalize_text(value)
    categories = [
        name for name, pattern in CATEGORY_RULES if re.search(pattern, normalized, re.IGNORECASE)
    ]
    if not categories:
        categories = ["other"]
    primary = categories[0]
    return categories, primary


def classify_depth(value: str, categories: list[str]) -> tuple[str, list[str]]:
    normalized = normalize_text(value)
    reasons: list[str] = []
    word_count = len(re.findall(r"[\w]+", normalized, re.UNICODE))
    has_norm_reference = bool(
        re.search(r"\b(?:сп|гост|фз|пп)\s*[№\d]|п\.\s*\d", normalized, re.IGNORECASE)
    )
    engineering = bool(set(categories) & ENGINEERING_CATEGORIES)
    if engineering:
        reasons.append("engineering_category")
    if has_norm_reference:
        reasons.append("normative_reference")
    if word_count >= 25:
        reasons.append("long_form")
    if len(categories) >= 2:
        reasons.append("multi_category")

    if engineering and (has_norm_reference or word_count >= 25 or len(categories) >= 2):
        return "substantial_candidate", reasons
    if set(categories) <= {"formatting", "clarification", "correction", "other"} and word_count <= 22:
        return "simple_candidate", reasons or ["short_non_engineering"]
    return "review_needed", reasons or ["insufficient_signal"]


def feature_row(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    categories, primary = classify_remark(normalized)
    depth, reasons = classify_depth(normalized, categories)
    return {
        "remark_hash": remark_hash(normalized),
        "char_count": len(normalized),
        "word_count": len(re.findall(r"[\w]+", normalized, re.UNICODE)),
        "primary_category_v0": primary,
        "categories_v0": "|".join(categories),
        "depth_class_v0": depth,
        "depth_reason_codes_v0": "|".join(reasons),
    }
