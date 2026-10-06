"""
Localization parity test suite adhering to [CS-LOCALIZATION].

Verifies that all language catalogs (en.json, pt_br.json) share identical keys
with non-empty string values.
"""

import json
import unittest
from pathlib import Path


class TestLocalizationParity(unittest.TestCase):
    """
    Automated test validating key parity across language dictionaries.
    """

    def setUp(self):
        self.loc_dir = Path(__file__).resolve().parent.parent / "data" / "localization"
        self.en_file = self.loc_dir / "en.json"
        self.pt_br_file = self.loc_dir / "pt_br.json"

    def test_catalogs_exist(self):
        """Ensure both default and secondary localization files exist."""
        self.assertTrue(self.en_file.exists(), "en.json missing")
        self.assertTrue(self.pt_br_file.exists(), "pt_br.json missing")

    def test_key_parity_and_non_empty(self):
        """Ensure identical key sets and non-empty translations."""
        with open(self.en_file, "r", encoding="utf-8") as f:
            en_data = json.load(f)

        with open(self.pt_br_file, "r", encoding="utf-8") as f:
            pt_br_data = json.load(f)

        en_keys = set(en_data.keys())
        pt_br_keys = set(pt_br_data.keys())

        missing_in_pt_br = en_keys - pt_br_keys
        extra_in_pt_br = pt_br_keys - en_keys

        self.assertEqual(
            missing_in_pt_br, set(),
            f"Keys missing in pt_br.json: {missing_in_pt_br}"
        )
        self.assertEqual(
            extra_in_pt_br, set(),
            f"Unexpected extra keys in pt_br.json: {extra_in_pt_br}"
        )

        for key, val in en_data.items():
            self.assertTrue(isinstance(val, str) and val.strip(), f"Empty string in en.json for {key}")

        for key, val in pt_br_data.items():
            self.assertTrue(isinstance(val, str) and val.strip(), f"Empty string in pt_br.json for {key}")


if __name__ == "__main__":
    unittest.main()
