import csv
import sys
import tempfile
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
    read_human_overrides,
)


class OrgAliasRegistryTests(unittest.TestCase):
    def test_extracts_quoted_name_from_homoglyph_variant(self) -> None:
        self.assertEqual(
            extract_quoted_name('"\u0419\u2039\u0419\u00ac\u0419\u0404\u0419\u0401\u0419\u0408 \u0419\u2020\u0419\u0401\u0419\u00a7\u0419\u00ac\u0419\u0459\u0419\u00a0 \u0419\u2039\u0419\u2030"'),
            '\u0441\u0442\u0440\u043e\u0439 \u043c\u043e\u043d\u0442\u0430\u0436 \u0441\u043f',
        )

    def test_detects_legal_form_and_identity_hint(self) -> None:
        self.assertEqual(
            detect_legal_form('000 \u00ab\u0421\u041f \u0421\u0422\u0420\u041e\u0419\u0418\u041d\u0412\u0415\u0421\u0422 \u0413\u0420\u0423\u041f\u041f\u00bb'),
            '\u041e\u041e\u041e',
        )
        key, display, legal_form = identity_hint(
            '000 \u00ab\u0421\u041f \u0421\u0422\u0420\u041e\u0419\u0418\u041d\u0412\u0415\u0421\u0422 \u0413\u0420\u0423\u041f\u041f\u00bb',
            '',
        )
        self.assertEqual(key, '\u0441\u043f \u0441\u0442\u0440\u043e\u0439\u0438\u043d\u0432\u0435\u0441\u0442 \u0433\u0440\u0443\u043f\u043f')
        self.assertEqual(display, '\u041e\u041e\u041e \u00ab\u0441\u043f \u0441\u0442\u0440\u043e\u0439\u0438\u043d\u0432\u0435\u0441\u0442 \u0433\u0440\u0443\u043f\u043f\u00bb')
        self.assertEqual(legal_form, '\u041e\u041e\u041e')

    def test_uses_raw_normalized_fallback_without_quotes(self) -> None:
        key, display, _legal_form = identity_hint(
            '\u041e\u0431\u0449\u0435\u0441\u0442\u0432\u043e \u0441 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u043d\u043e\u0439 \u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0441\u0442\u044c\u044e \u0412\u0410\u0422\u0410\u0413\u0410',
            '',
        )
        self.assertEqual(key, '\u0432\u0430\u0442\u0430\u0433\u0430')
        self.assertIn('\u0432\u0430\u0442\u0430\u0433\u0430', display)

    def test_uses_capremont_object_key_and_registry_match(self) -> None:
        self.assertEqual(object_registry_key('1830_25'), '183025')
        self.assertEqual(match_registry_name('\u0432\u0438\u0442\u043c\u0430\u0440', 'lead_designer', '\u0412\u0438\u0442\u043c\u0430\u0440', ''), '\u0412\u0438\u0442\u043c\u0430\u0440')
        self.assertEqual(match_registry_name('\u0441\u0442\u0440\u043e\u0439 \u043c\u043e\u043d\u0442\u0430\u0436 \u0441\u043f', 'lead_designer', '\u0421\u0442\u0440\u043e\u0439\u041c\u043e\u043d\u0442\u0430\u0436 \u0421\u041f', ''), '\u0421\u0442\u0440\u043e\u0439\u041c\u043e\u043d\u0442\u0430\u0436 \u0421\u041f')
        self.assertEqual(match_registry_name('\u0441\u043f\u0435\u043a\u0442\u0440', 'subcontractor', '\u0421\u043f\u0435\u043a\u0442\u0440', '\u041b\u0413\u0416\u0422'), '\u0421\u043f\u0435\u043a\u0442\u0440')
        self.assertEqual(match_registry_name('\u043b\u0433\u0436\u0442', 'lead_designer', '\u0421\u043f\u0435\u043a\u0442\u0440', '\u041b\u0413\u0416\u0422'), '\u041b\u0413\u0416\u0422')

    def test_reads_human_overrides_by_alias_and_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / 'overrides.csv'
            with path.open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        'alias_id',
                        'organization_identity_hint',
                        'canonical_display_override',
                        'notes',
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        'alias_id': 'org_alias_v0_003',
                        'organization_identity_hint': '\u0432\u0430\u0442\u0430\u0433\u0430',
                        'canonical_display_override': '\u0412\u0430\u0442\u0430\u0433\u0430',
                        'notes': 'confirmed',
                    }
                )
            by_alias, by_hint = read_human_overrides(path)
            self.assertEqual(by_alias['org_alias_v0_003']['canonical_display_override'], '\u0412\u0430\u0442\u0430\u0433\u0430')
            self.assertEqual(by_hint['\u0432\u0430\u0442\u0430\u0433\u0430']['notes'], 'confirmed')


if __name__ == '__main__':
    unittest.main()
