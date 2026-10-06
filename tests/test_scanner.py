"""
Mod scanner test suite adhering to [CS-NO-MOCK].

Creates concrete sample mod file structures on disk and verifies accurate discovery,
grouping, and vanilla target resolution.
"""

import unittest
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge_base import VanillaKnowledgeBase
from src.scanner import ModScanner
from src.models import EquipmentSlot


class TestModScanner(unittest.TestCase):
    """
    Tests discovery and parsing of actual .partsbnd.dcx file trees.
    """

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.kb = VanillaKnowledgeBase.from_data_dir(str(self.root_dir / "data"))
        self.scanner = ModScanner(self.kb)

        self.test_dir = Path(__file__).resolve().parent / "tmp_scanner_test"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # Create sample armor mod folder (Carian Knight replacer: model 4000)
        carian_dir = self.test_dir / "BerserkArmor" / "parts"
        carian_dir.mkdir(parents=True, exist_ok=True)
        for part in ["am_m_4000.partsbnd.dcx", "bd_m_4000.partsbnd.dcx", "hd_m_4000.partsbnd.dcx", "lg_m_4000.partsbnd.dcx"]:
            with open(carian_dir / part, "wb") as f:
                f.write(b"MOCK_PARTSBND_DCX_PAYLOAD")

        # Create sample weapon mod file (Moonveil replacer: model 0415)
        weapon_dir = self.test_dir / "YamatoKatana"
        weapon_dir.mkdir(parents=True, exist_ok=True)
        with open(weapon_dir / "wp_a_0415.partsbnd.dcx", "wb") as f:
            f.write(b"MOCK_WEAPON_DCX_PAYLOAD")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_scan_and_grouping(self):
        """Verifies discovered mod sets, target names, and slot assignments."""
        detected = self.scanner.scan_directory(str(self.test_dir))
        self.assertEqual(len(detected), 2)

        # Find armor set
        armor_set = next((s for s in detected if s.target_model_id == "4000"), None)
        self.assertIsNotNone(armor_set)
        self.assertEqual(armor_set.target_vanilla_name, "Carian Knight Set")
        self.assertEqual(len(armor_set.parts), 4)
        slots = {p.slot for p in armor_set.parts}
        self.assertEqual(slots, {EquipmentSlot.ARMS, EquipmentSlot.BODY, EquipmentSlot.HEAD, EquipmentSlot.LEGS})

        # Find weapon set
        weapon_set = next((s for s in detected if s.target_model_id == "0415"), None)
        self.assertIsNotNone(weapon_set)
        self.assertEqual(weapon_set.target_vanilla_name, "Moonveil")
        self.assertTrue(weapon_set.is_weapon)


if __name__ == "__main__":
    unittest.main()
