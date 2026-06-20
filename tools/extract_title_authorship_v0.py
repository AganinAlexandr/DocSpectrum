#!/usr/bin/env python3
"""Extract title-page organization/GIP parties from explorer bundles."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from text_features import normalize_text, text_tokens


DEFAULT_SELECTION = Path(
    r"E:\output\DocSpectrum\gip_pdf_selection_v0\gip_authorship_pdf_selection_v0.csv"
)
DEFAULT_EXPORT_DIR = Path(r"E:\output\pdf-structure-explorer\exports")
DEFAULT_DETECTOR = Path(
    r"C:\Users\alexa\Cursor\Checker87 app\pp87-checker\tools_heading\title_zone.py"
)
DEFAULT_OUTPUT_DIR = Path(r"E:\output\DocSpectrum\title_authorship_v0")
DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEFAULT_TESSDATA = Path(r"C:\Users\alexa\Cursor\OCR_docs\tessdata")

ORG_RE = re.compile(
    r"\b(?:ООО|АО|ПАО|ОАО|ЗАО|МУП|ГУП|ГБУ|ГКУ|МБУ|ИП|"
    r"общество\s+с\s+ограниченной\s+ответственностью|"
    r"акционерное\s+общество)\b",
    re.IGNORECASE,
)
GIP_RE = re.compile(
    r"(?:^|\W)(?:ГИП|главн\w*\s+инженер\w*\s+проекта)(?:$|\W)",
    re.IGNORECASE,
)
ORG_RE = re.compile(
    ORG_RE.pattern
    + r"|(?:^|\W)(?:ооо|000)(?:$|\W)"
    + r"|(?:^|\W)о[бд]щество\s+с\s+ограниченн\w*\s+ответственност\w*(?:$|\W)",
    re.IGNORECASE,
)
GIP_RE = re.compile(
    GIP_RE.pattern
    + r"|(?:^|\W)(?:г|т)ла[бв]н\w*\s+инженер\w*\s+проект\w*(?:$|\W)"
    + r"|(?:^|\W)(?:г|т)ла[бв]н\w*\s+инженер\w*\s+прое",
    re.IGNORECASE,
)
PERSON_RE = re.compile(
    r"\b([А-ЯЁ][а-яё-]{2,})\s+"
    r"([А-ЯЁ])\.?\s*([А-ЯЁ])?\.?\b"
)
PERSON_PREFIX_RE = re.compile(
    r"\b([А-ЯЁ])\.?\s*([А-ЯЁ])?\.?\s+"
    r"([А-ЯЁ][а-яё-]{2,})\b"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_detector(path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("docspectrum_title_zone", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load title detector from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def group_title_pages(pages: list[int]) -> list[list[int]]:
    ordered = sorted(set(pages))
    if not ordered:
        return []
    # Правило (human 19-06): Заказчик/Генподрядчик = первые 2 титула, исполнитель
    # (реальный автор, HC-013) = ВСЁ остальное. Раньше 3-стр.зона (1;2;3) не делилась
    # → субподрядчик терялся. Теперь при >2 страницах делим строго first-2 / rest.
    if len(ordered) <= 2:
        return [ordered]
    return [ordered[:2], ordered[2:]]


def visual_lines(bundle: Path, pages: list[int]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in read_csv(bundle / "text_segments.csv")
        if int(row["page_number"]) in pages
        and (row.get("text_value") or "").strip()
    ]
    grouped: dict[tuple[int, int], list[dict[str, str]]] = {}
    for row in rows:
        key = (int(row["page_number"]), round(float(row["y1"])))
        grouped.setdefault(key, []).append(row)
    lines = []
    for (page, y), items in sorted(grouped.items()):
        items.sort(key=lambda row: float(row["x1"]))
        text = " ".join(item["text_value"].strip() for item in items)
        lines.append(
            {
                "page_number": page,
                "y": y,
                "text": text,
                "normalized": normalize_text(text),
            }
        )
    return lines


def ocr_page_lines(
    pdf_path: Path,
    page_number: int,
    work_dir: Path,
    tesseract_path: Path,
    tessdata_path: Path,
) -> list[dict[str, Any]]:
    """Render one page and OCR it without adding Pillow/pytesseract dependencies."""
    import fitz

    work_dir.mkdir(parents=True, exist_ok=True)
    image_path = work_dir / f"{pdf_path.stem}_{page_number}.png"
    document = fitz.open(pdf_path)
    try:
        pixmap = document[page_number - 1].get_pixmap(dpi=250, alpha=False)
        pixmap.save(image_path)
    finally:
        document.close()

    try:
        result = subprocess.run(
            [
                str(tesseract_path),
                str(image_path),
                "stdout",
                "-l",
                "rus",
                "--psm",
                "6",
                "--tessdata-dir",
                str(tessdata_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        image_path.unlink(missing_ok=True)

    return [
        {
            "page_number": page_number,
            "y": index * 20,
            "text": text,
            "normalized": normalize_text(text),
            "line_source": "ocr_cli",
        }
        for index, raw in enumerate(result.stdout.splitlines(), start=1)
        if (text := raw.strip())
    ]


def recover_image_title_pages(
    pdf_path: Path,
    cover_end: int,
    work_dir: Path,
    tesseract_path: Path,
    tessdata_path: Path,
) -> tuple[list[int], dict[int, list[dict[str, Any]]]]:
    if (
        cover_end <= 0
        or not tesseract_path.is_file()
        or not tessdata_path.is_dir()
    ):
        return [], {}
    lines_by_page = {
        page_number: ocr_page_lines(
            pdf_path,
            page_number,
            work_dir,
            tesseract_path,
            tessdata_path,
        )
        for page_number in range(1, cover_end + 1)
    }
    # The shared detector has already established a leading image-title zone.
    # OCR recovers its text; it does not independently infer a new zone.
    return list(range(1, cover_end + 1)), lines_by_page


def candidate_line_windows(
    lines: list[dict[str, Any]],
    max_size: int = 3,
) -> list[dict[str, Any]]:
    """Join adjacent OCR fragments so split legal names remain detectable."""
    windows = list(lines)
    page_numbers = sorted({line["page_number"] for line in lines})
    orders = [lines]
    orders.extend(
        list(reversed(
            [line for line in lines if line["page_number"] == page_number]
        ))
        for page_number in page_numbers
    )
    for ordered_lines in orders:
        for index, line in enumerate(ordered_lines):
            same_page = [
                item
                for item in ordered_lines[index : index + max_size]
                if item["page_number"] == line["page_number"]
            ]
            for size in range(2, len(same_page) + 1):
                items = same_page[:size]
                text = " ".join(item["text"] for item in items)
                windows.append(
                    {
                        "page_number": line["page_number"],
                        "y": min(item["y"] for item in items),
                        "text": text,
                        "normalized": normalize_text(text),
                    }
                )
    return windows


SECTION_FIVE_SUBSECTIONS = (
    ("ЭС", "Система электроснабжения"),
    ("ВС", "Система водоснабжения"),
    ("ВО", "Система водоотведения"),
    ("ВК", "Система водоснабжения и водоотведения"),
    ("ОВ", "Отопление, вентиляция и кондиционирование воздуха"),
    ("СС", "Сети связи"),
    ("ГС", "Система газоснабжения"),
)

PP87_SECTION_TITLES = (
    ("ПЗ", "Пояснительная записка", ("Пояснительная записка",)),
    (
        "СПОЗУ",
        "Схема планировочной организации земельного участка",
        ("Схема планировочной организации земельного участка",),
    ),
    (
        "АР",
        "Объемно-планировочные и архитектурные решения",
        (
            "Объемно-планировочные и архитектурные решения",
            "Архитектурные решения",
        ),
    ),
    ("КР", "Конструктивные решения", ("Конструктивные решения",)),
    (
        "ООС",
        "Мероприятия по охране окружающей среды",
        ("Мероприятия по охране окружающей среды",),
    ),
    (
        "ПОС",
        "Проект организации строительства",
        (
            "Проект организации строительства",
            "Проект организации капитального ремонта",
        ),
    ),
    (
        "ПБ",
        "Мероприятия по обеспечению пожарной безопасности",
        ("Мероприятия по обеспечению пожарной безопасности",),
    ),
    (
        "ТБЭ",
        "Требования к безопасной эксплуатации",
        (
            "Требования к безопасной эксплуатации",
            "Требования к обеспечению безопасной эксплуатации",
        ),
    ),
    (
        "ОДИ",
        "Мероприятия по обеспечению доступа инвалидов",
        ("Мероприятия по обеспечению доступа инвалидов",),
    ),
    (
        "СМ",
        "Смета на строительство",
        (
            "Смета на строительство",
            "Смета на капитальный ремонт",
        ),
    ),
)

SECTION_TITLE_STOP_RE = re.compile(
    r"\b(?:том|шифр|заказчик|застройщик|гип|главн\w*\s+инженер|"
    r"генеральн\w*\s+директор|проверил|разработал|дата)\b",
)
SECTION_MATCH_STOPWORDS = {
    "подраздел",
    "система",
    "раздел",
}


def section_title_tokens(value: str) -> list[str]:
    return [
        token
        for token in text_tokens(normalize_text(value))
        if not token.isdigit() and token not in SECTION_MATCH_STOPWORDS
    ]


def token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if min(len(left), len(right)) >= 6 and left[:6] == right[:6]:
        return 0.95
    return SequenceMatcher(None, left, right).ratio()


def subsection_match_score(value: str, canonical_name: str) -> float:
    observed = section_title_tokens(value)
    expected = section_title_tokens(canonical_name)
    if not observed or not expected:
        return 0.0

    matched = sum(
        max(token_similarity(expected_token, observed_token) for observed_token in observed)
        >= 0.82
        for expected_token in expected
    )
    token_recall = matched / len(expected)
    token_precision = matched / len(observed)
    normalized_observed = " ".join(observed)
    normalized_expected = " ".join(expected)
    phrase_score = SequenceMatcher(
        None,
        normalized_expected,
        normalized_observed,
    ).ratio()
    return round(
        0.65 * token_recall + 0.25 * token_precision + 0.10 * phrase_score,
        6,
    )


def match_title_name(
    value: str,
    candidates: tuple[tuple[str, str], ...],
    field_prefix: str,
) -> dict[str, str]:
    ranked = sorted(
        (
            (subsection_match_score(value, name), code, name)
            for code, name in candidates
        ),
        reverse=True,
    )
    best_score, best_code, best_name = ranked[0]
    second_score, second_code, second_name = ranked[1]
    margin = best_score - second_score
    resolved = best_score >= 0.62 and margin >= 0.10
    return {
        f"{field_prefix}_match_code": best_code if resolved else "",
        f"{field_prefix}_match_name": best_name if resolved else "",
        f"{field_prefix}_match_score": f"{best_score:.6f}",
        f"{field_prefix}_second_code": second_code,
        f"{field_prefix}_second_name": second_name,
        f"{field_prefix}_second_score": f"{second_score:.6f}",
        f"{field_prefix}_match_margin": f"{margin:.6f}",
        f"{field_prefix}_match_status": (
            "resolved"
            if resolved
            else "ambiguous"
            if best_score >= 0.45
            else "insufficient"
        ),
    }


def match_section_five_subsection(value: str) -> dict[str, str]:
    return match_title_name(
        value,
        SECTION_FIVE_SUBSECTIONS,
        "declared_subsection",
    )


def empty_title_match(field_prefix: str) -> dict[str, str]:
    return {
        f"{field_prefix}_match_code": "",
        f"{field_prefix}_match_name": "",
        f"{field_prefix}_match_score": "",
        f"{field_prefix}_second_code": "",
        f"{field_prefix}_second_name": "",
        f"{field_prefix}_second_score": "",
        f"{field_prefix}_match_margin": "",
        f"{field_prefix}_match_status": "not_evaluated",
    }


def match_pp87_section(value: str) -> dict[str, str]:
    ranked = sorted(
        (
            (
                max(subsection_match_score(value, alias) for alias in aliases),
                code,
                canonical_name,
            )
            for code, canonical_name, aliases in PP87_SECTION_TITLES
        ),
        reverse=True,
    )
    best_score, best_code, best_name = ranked[0]
    second_score, second_code, second_name = ranked[1]
    margin = best_score - second_score
    resolved = best_score >= 0.62 and margin >= 0.10
    return {
        "declared_section_match_code": best_code if resolved else "",
        "declared_section_match_name": best_name if resolved else "",
        "declared_section_match_score": f"{best_score:.6f}",
        "declared_section_second_code": second_code,
        "declared_section_second_name": second_name,
        "declared_section_second_score": f"{second_score:.6f}",
        "declared_section_match_margin": f"{margin:.6f}",
        "declared_section_match_status": (
            "resolved"
            if resolved
            else "ambiguous"
            if best_score >= 0.45
            else "insufficient"
        ),
    }


def collect_title_block(
    scoped: list[dict[str, Any]],
    start_index: int,
    max_following_lines: int = 4,
) -> list[str]:
    first = scoped[start_index]
    page_number = first["page_number"]
    result = [first["text"].strip()]
    for row in scoped[start_index + 1 : start_index + 1 + max_following_lines]:
        if row["page_number"] != page_number:
            break
        text = row["text"].strip()
        normalized = normalize_text(text)
        if (
            re.search(r"\b(?:раздел|подраздел)\s*(?:№\s*)?\d", normalized)
            or SECTION_TITLE_STOP_RE.search(normalized)
        ):
            break
        result.append(text)
    return list(dict.fromkeys(result))


def extract_declared_section(lines: list[dict[str, Any]]) -> dict[str, str]:
    ordered = sorted(lines, key=lambda row: (row["page_number"], row["y"]))
    normalized = [normalize_text(row["text"]) for row in ordered]
    anchor_indices = [
        index for index, text in enumerate(normalized)
        if "проектная документация" in text
    ]
    start = anchor_indices[0] if anchor_indices else 0
    scoped = ordered[start : start + 35]

    section_lines: list[str] = []
    subsection_lines: list[str] = []
    section_number = ""
    subsection_number = ""
    for index, row in enumerate(scoped):
        text = row["text"].strip()
        normalized_text = normalize_text(text)
        section_match = re.search(
            r"\bраздел\s*(?:№\s*)?(\d+(?:\.\d+)*)",
            normalized_text,
        )
        subsection_match = re.search(
            r"\bподраздел\s*(?:№\s*)?(\d+(?:\.\d+)*)",
            normalized_text,
        )
        if subsection_match:
            if not subsection_lines:
                subsection_lines = collect_title_block(scoped, index)
        elif section_match:
            if not section_lines:
                section_lines = collect_title_block(scoped, index)
        if section_match and not section_number:
            section_number = section_match.group(1)
        if subsection_match and not subsection_number:
            subsection_number = subsection_match.group(1)

    declared_text = " | ".join(dict.fromkeys(section_lines))
    declared_subsection_text = " | ".join(dict.fromkeys(subsection_lines))
    subsection_match = (
        match_section_five_subsection(declared_subsection_text)
        if section_number.split(".", 1)[0] == "5" and declared_subsection_text
        else empty_title_match("declared_subsection")
    )
    section_match = (
        match_pp87_section(declared_text)
        if section_number and section_number.split(".", 1)[0] != "5"
        else empty_title_match("declared_section")
    )
    canonical = (
        subsection_match["declared_subsection_match_code"]
        or section_match["declared_section_match_code"]
    )
    return {
        "declared_section_number": section_number,
        "declared_section_text": declared_text,
        "declared_subsection_number": subsection_number,
        "declared_subsection_text": declared_subsection_text,
        "declared_section_kind": canonical,
        **section_match,
        **subsection_match,
        "declared_section_status": (
            "resolved_from_title"
            if canonical
            else "subsection_text_found_kind_ambiguous"
            if declared_subsection_text
            else "section_text_only"
            if declared_text
            else "not_found"
        ),
    }


def canonical_section_kind(value: str) -> str:
    return match_section_five_subsection(value)["declared_subsection_match_code"]


def clean_organization_name(text: str) -> str:
    quoted = re.search(r"«\s*([^»]{2,}?)\s*»", text)
    if not quoted:
        quoted = re.search(r"[\"“]\s*([^\"”]{2,}?)\s*[\"”]", text)
    if not quoted:
        return text.strip()
    name = quoted.group(1).strip()
    prefix_text = text[: quoted.start()]
    prefixes = list(
        re.finditer(
            r"(?:ООО|000|АО|ПАО|ОАО|ЗАО|МУП|ГУП|ИП)(?:\s+[А-ЯA-Z]{1,4})?",
            prefix_text,
            re.IGNORECASE,
        )
    )
    prefix = prefixes[-1].group(0).strip() if prefixes else ""
    if prefix == "000":
        prefix = "ООО"
    return f"{prefix} «{name}»".strip()


def organization_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for line in candidate_line_windows(lines):
        legal_form_match = bool(ORG_RE.search(line["text"]))
        quoted_name_match = bool(
            re.search(r"[«\"“].{2,}[»\"”]", line["text"])
            and len(line["text"]) <= 120
            and not re.search(
                r"\b(?:банк|заказчик|капитальн|раздел|документац)\w*",
                line["normalized"],
            )
        )
        if not legal_form_match and not quoted_name_match:
            continue
        clean_name = clean_organization_name(line["text"])
        key = normalize_text(clean_name)
        item = candidates.setdefault(
            key,
            {
                "organization_name_raw": clean_name,
                "organization_name_normalized": key,
                "organization_evidence_text": line["text"],
                "pages": set(),
                "occurrence_count": 0,
                "min_y": line["y"],
                "legal_form_match": legal_form_match,
                "has_quoted_name": bool(
                    re.search(r"[«\"“].{2,}[»\"”]", line["text"])
                ),
            },
        )
        item["pages"].add(line["page_number"])
        item["occurrence_count"] += 1
        item["min_y"] = min(item["min_y"], line["y"])
    result = []
    for item in candidates.values():
        item["pages"] = sorted(item["pages"])
        result.append(item)
    result.sort(
        key=lambda item: (
            -len(item["pages"]),
            -int(item["has_quoted_name"]),
            -int(item["legal_form_match"]),
            item["min_y"],
            -item["occurrence_count"],
            item["organization_name_normalized"],
        )
    )
    return result


def person_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for index, line in enumerate(lines):
        if not GIP_RE.search(line["normalized"]):
            continue
        nearby = [
            candidate
            for candidate in lines
            if candidate["page_number"] == line["page_number"]
            and abs(candidate["y"] - line["y"]) <= 80
        ]
        matches = []
        for candidate in nearby:
            person_matches = [
                (
                    match.group(1),
                    "".join(value for value in match.groups()[1:] if value),
                    match.group(0),
                )
                for match in PERSON_RE.finditer(candidate["text"])
            ]
            person_matches.extend(
                (
                    match.group(3),
                    "".join(value for value in match.groups()[:2] if value),
                    match.group(0),
                )
                for match in PERSON_PREFIX_RE.finditer(candidate["text"])
            )
            for surname, initials, raw_name in person_matches:
                matches.append(
                    {
                        "gip_name_raw": raw_name,
                        "gip_surname_normalized": normalize_text(surname),
                        "gip_initials": initials,
                        "page_number": candidate["page_number"],
                        "distance_y": abs(candidate["y"] - line["y"]),
                        "evidence_text": candidate["text"],
                    }
                )
        matches.sort(
            key=lambda item: (
                item["distance_y"],
                item["gip_surname_normalized"],
            )
        )
        results.extend(matches[:3])
    deduped = {}
    for item in results:
        key = (
            item["gip_surname_normalized"],
            item["gip_initials"],
            item["page_number"],
        )
        current = deduped.get(key)
        if current is None or item["distance_y"] < current["distance_y"]:
            deduped[key] = item
    return sorted(
        deduped.values(),
        key=lambda item: (
            item["distance_y"],
            item["page_number"],
            item["gip_surname_normalized"],
        ),
    )


def select_party(
    organizations: list[dict[str, Any]],
    people: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    organization = organizations[0] if organizations else None
    person = people[0] if people else None
    if organization and person and len(organizations) == 1:
        return organization, person, "high"
    if organization and person:
        return organization, person, "medium"
    return organization, person, "low"


def build(
    selection_path: Path,
    export_dir: Path,
    detector_path: Path,
    output_dir: Path,
    tesseract_path: Path = DEFAULT_TESSERACT,
    tessdata_path: Path = DEFAULT_TESSDATA,
) -> dict[str, Any]:
    detector = load_detector(detector_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    selections = read_csv(selection_path)
    document_rows: list[dict[str, Any]] = []
    party_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    for selection in selections:
        bundle = export_dir / selection["expected_document_id"]
        pdf_path = Path(selection["authorship_source_pdf"])
        detection = detector.detect_title_zone(bundle, pdf_path=pdf_path)
        title_pages = [int(page) for page in detection["title_pages"]]
        ocr_lines_by_page: dict[int, list[dict[str, Any]]] = {}
        base_source = detection["source"]
        base_anomaly = detection["anomaly"] or ""
        if not title_pages and detection["anomaly"] == "image_title":
            title_pages, ocr_lines_by_page = recover_image_title_pages(
                pdf_path,
                int(detection["cover_end"]),
                output_dir / "_ocr_tmp",
                tesseract_path,
                tessdata_path,
            )
            if title_pages:
                detection = {
                    **detection,
                    "source": "ocr_cli",
                    "anomaly": "title_ocr_recovered_cli",
                }
        groups = group_title_pages(title_pages)
        title_lines = [
            line
            for page_number in title_pages
            for line in ocr_lines_by_page.get(page_number, [])
        ]
        if not title_lines and title_pages:
            title_lines = visual_lines(bundle, title_pages)
        declared_section = extract_declared_section(title_lines)
        selected_section_code = selection.get("section_code", "")
        title_section_code = declared_section["declared_section_kind"]
        effective_section_code = title_section_code or selected_section_code
        section_code_status = (
            "title_matches_selection"
            if title_section_code and title_section_code == selected_section_code
            else "title_overrides_selection"
            if title_section_code
            else "selection_fallback"
        )
        structure_status = (
            "single_party_expected"
            if len(groups) == 1 and len(title_pages) == 2
            else "lead_and_subcontractor_expected"
            if len(groups) == 2 and len(title_pages) == 4
            else "manual_review_title_structure"
        )
        document_rows.append(
            {
                **selection,
                "cover_end": detection["cover_end"],
                "title_pages": ";".join(map(str, title_pages)),
                "title_page_count": len(title_pages),
                "title_detection_source": detection["source"],
                "title_anomaly": detection["anomaly"] or "",
                "title_detection_base_source": base_source,
                "title_detection_base_anomaly": base_anomaly,
                "title_structure_status": structure_status,
                "party_group_count": len(groups),
                "section_code_selected": selected_section_code,
                "section_code_title": title_section_code,
                "section_code_effective": effective_section_code,
                "section_code_resolution_status": section_code_status,
                **declared_section,
            }
        )

        for group_index, pages in enumerate(groups, start=1):
            lines = [
                line
                for page_number in pages
                for line in ocr_lines_by_page.get(page_number, [])
            ]
            if not lines:
                lines = visual_lines(bundle, pages)
            organizations = organization_candidates(lines)
            people = person_candidates(lines)
            organization, person, confidence = select_party(
                organizations,
                people,
            )
            role = (
                "lead_designer"
                if group_index == 1 and len(groups) >= 1
                else "subcontractor"
                if group_index == 2 and len(groups) == 2
                else "unresolved"
            )
            party_id = (
                f"{selection['object_id']}__{selection['section_code']}"
                f"__party_{group_index}"
            )
            party_rows.append(
                {
                    "party_id": party_id,
                    "object_id": selection["object_id"],
                    "document_id": selection["expected_document_id"],
                    "crc32": selection["crc32"],
                    "section_code": selection["section_code"],
                    "title_page_numbers": ";".join(map(str, pages)),
                    "role": role,
                    "organization_name_raw": (
                        organization["organization_name_raw"]
                        if organization
                        else ""
                    ),
                    "organization_name_normalized": (
                        organization["organization_name_normalized"]
                        if organization
                        else ""
                    ),
                    "organization_candidate_count": len(organizations),
                    "organization_evidence_text": (
                        organization["organization_evidence_text"]
                        if organization
                        else ""
                    ),
                    "gip_name_raw": person["gip_name_raw"] if person else "",
                    "gip_surname_normalized": (
                        person["gip_surname_normalized"] if person else ""
                    ),
                    "gip_initials": person["gip_initials"] if person else "",
                    "gip_candidate_count": len(people),
                    "extraction_confidence": confidence,
                    "effective_author": role in {
                        "subcontractor",
                        "lead_designer",
                    }
                    and (
                        role == "subcontractor"
                        or len(groups) == 1
                    ),
                    "effective_author_rule": (
                        "subcontractor_actual_author"
                        if role == "subcontractor"
                        else "sole_designer_author"
                        if len(groups) == 1
                        else "lead_contractual_not_effective_author"
                    ),
                    "manual_review_required": (
                        confidence != "high"
                        or structure_status == "manual_review_title_structure"
                    ),
                }
            )
            for line in lines:
                evidence_rows.append(
                    {
                        "party_id": party_id,
                        "object_id": selection["object_id"],
                        "section_code": selection["section_code"],
                        "page_number": line["page_number"],
                        "y": line["y"],
                        "text": line["text"],
                    }
                )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        output_dir / "title_authorship_documents_v0.csv",
        document_rows,
        list(document_rows[0]),
    )
    write_csv(
        output_dir / "title_authorship_parties_v0.csv",
        party_rows,
        list(party_rows[0]),
    )
    write_csv(
        output_dir / "title_authorship_evidence_v0.csv",
        evidence_rows,
        list(evidence_rows[0]),
    )
    summary = {
        "schema_version": "title_authorship_v0",
        "generated_at": generated_at,
        "document_count": len(document_rows),
        "party_count": len(party_rows),
        "title_page_count_distribution": dict(
            sorted(
                Counter(row["title_page_count"] for row in document_rows).items()
            )
        ),
        "title_structure_counts": dict(
            sorted(
                Counter(
                    row["title_structure_status"] for row in document_rows
                ).items()
            )
        ),
        "party_role_counts": dict(
            sorted(Counter(row["role"] for row in party_rows).items())
        ),
        "confidence_counts": dict(
            sorted(
                Counter(row["extraction_confidence"] for row in party_rows).items()
            )
        ),
        "manual_review_party_count": sum(
            bool(row["manual_review_required"]) for row in party_rows
        ),
        "effective_author_count": sum(
            bool(row["effective_author"]) for row in party_rows
        ),
        "rules": [
            "title pages are detected by the shared Checker detector.",
            "image-title text is recovered by the DocSpectrum Tesseract CLI adapter.",
            "two consecutive title pages normally form one party.",
            "four consecutive title pages normally form lead and subcontractor parties.",
            "page position is a role feature, not sole proof.",
            "all ambiguous organization/GIP candidates require review.",
        ],
        "files": {
            "documents": "title_authorship_documents_v0.csv",
            "parties": "title_authorship_parties_v0.csv",
            "evidence": "title_authorship_evidence_v0.csv",
        },
    }
    (output_dir / "title_authorship_v0.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract organization/GIP parties from title pages."
    )
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--detector", type=Path, default=DEFAULT_DETECTOR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tesseract", type=Path, default=DEFAULT_TESSERACT)
    parser.add_argument("--tessdata", type=Path, default=DEFAULT_TESSDATA)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.selection,
                args.export_dir,
                args.detector,
                args.output_dir,
                args.tesseract,
                args.tessdata,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
