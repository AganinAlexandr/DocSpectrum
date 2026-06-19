import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_org_alias_registry_v0 import (  # noqa: E402
    detect_legal_form,
    extract_quoted_name,
    identity_hint,
    match_registry_name,
    object_registry_key,
)


class OrgAliasRegistryTests(unittest.TestCase):
    def test_extracts_quoted_name_from_homoglyph_variant(self) -> None:
        self.assertEqual(
            extract_quoted_name('"ɋɬɪɨɣ Ɇɨɧɬɚɠ ɋɉ"'),
            "строй монтаж сп",
        )

    def test_detects_legal_form_and_identity_hint(self) -> None:
        self.assertEqual(detect_legal_form("000 «СП СТРОЙИНВЕСТ ГРУПП»"), "ООО")
        key, display, legal_form = identity_hint(
            "000 «СП СТРОЙИНВЕСТ ГРУПП»",
            "",
        )
        self.assertEqual(key, "сп стройинвест групп")
        self.assertEqual(display, "ООО «сп стройинвест групп»")
        self.assertEqual(legal_form, "ООО")

    def test_uses_raw_normalized_fallback_without_quotes(self) -> None:
        key, display, _legal_form = identity_hint(
            "Общество с ограниченной ответственностью ВАТАГА",
            "",
        )
        self.assertEqual(key, "ватага")
        self.assertIn("ватага", display)

    def test_uses_capremont_object_key_and_registry_match(self) -> None:
        self.assertEqual(object_registry_key("1830_25"), "183025")
        self.assertEqual(
            match_registry_name(
                "витмар",
                "lead_designer",
                "Витмар",
                "",
            ),
            "Витмар",
        )
        self.assertEqual(
            match_registry_name(
                "строй монтаж сп",
                "lead_designer",
                "СтройМонтаж СП",
                "",
            ),
            "СтройМонтаж СП",
        )
        self.assertEqual(
            match_registry_name(
                "спектр",
                "subcontractor",
                "Спектр",
                "ЛГЖТ",
            ),
            "Спектр",
        )
        self.assertEqual(
            match_registry_name(
                "лгжт",
                "lead_designer",
                "Спектр",
                "ЛГЖТ",
            ),
            "ЛГЖТ",
        )


if __name__ == "__main__":
    unittest.main()
