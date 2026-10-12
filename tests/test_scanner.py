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

    def test_gender_restriction_marking(self):
        """Verifies single-gender armor sets are identified and tagged in patch specs."""
        from src.param_builder import ParamBuilder
        from src.models import StandaloneAllocation, LootTarget, LootDistributionType

        female_dir = self.test_dir / "ShortSkirts" / "parts"
        female_dir.mkdir(parents=True, exist_ok=True)
        with open(female_dir / "bd_f_1160.partsbnd.dcx", "wb") as f:
            f.write(b"FEMALE_ARMOR_PAYLOAD")

        detected = self.scanner.scan_directory(str(self.test_dir))
        skirt_set = next((s for s in detected if s.target_model_id == "1160"), None)
        self.assertIsNotNone(skirt_set)
        self.assertEqual(skirt_set.gender_restriction, "female")

        skirt_set.allocation = StandaloneAllocation(
            new_model_id="9007",
            new_equip_param_id=9007000,
            new_item_lot_id=9100007,
            marker_tag="[LootForge]"
        )
        skirt_set.loot_target = LootTarget(
            route_type=LootDistributionType.ENEMY_DROP,
            target_id="431100000",
            display_name="Godrick Soldier",
            chance_or_cost=100.0
        )

        builder = ParamBuilder()
        spec = builder.build_patch_spec(skirt_set)

        fmg_spec = spec["fmg_texts"][0]
        self.assertIn("[Female Only]", fmg_spec["name"])
        self.assertIn("[RESTRICTION: Female Only]", fmg_spec["caption"])

        equip_spec = spec["equip_params"][0]
        self.assertEqual(equip_spec["field_updates"].get("equipModelGender"), 2)

        # Also verify non-female (standard/male parts) retains default naming without male tag
        male_dir = self.test_dir / "PlateArmor" / "parts"
        male_dir.mkdir(parents=True, exist_ok=True)
        with open(male_dir / "bd_m_1570.partsbnd.dcx", "wb") as f:
            f.write(b"MALE_ARMOR_PAYLOAD")

        detected = self.scanner.scan_directory(str(self.test_dir))
        plate_set = next((s for s in detected if s.target_model_id == "1570"), None)
        self.assertIsNotNone(plate_set)
        self.assertIsNone(plate_set.gender_restriction)

        plate_set.allocation = StandaloneAllocation(
            new_model_id="9008",
            new_equip_param_id=9008000,
            new_item_lot_id=9100008,
            marker_tag="[LootForge]"
        )
        plate_spec = builder.build_patch_spec(plate_set)
        plate_fmg = plate_spec["fmg_texts"][0]
        self.assertNotIn("[Male Only]", plate_fmg["name"])
        self.assertNotIn("[Female Only]", plate_fmg["name"])
        plate_equip = plate_spec["equip_params"][0]
        self.assertNotIn("equipModelGender", plate_equip["field_updates"])


if __name__ == "__main__":
    unittest.main()

