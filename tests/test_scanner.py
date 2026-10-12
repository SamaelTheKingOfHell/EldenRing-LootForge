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

    def test_cross_gender_compatibility(self):
        """Verifies single-gender armor sets are forged as unisex and cross-mirrored for both body types."""
        from src.param_builder import ParamBuilder
        from src.models import StandaloneAllocation, LootTarget, LootDistributionType
        from src.asset_renumberer import AssetRenumberer
        from src.parts_deployer import PartsDeployer

        # 1. Single-gender female mod (bd_f_1160)
        female_dir = self.test_dir / "ShortSkirts" / "parts"
        female_dir.mkdir(parents=True, exist_ok=True)
        with open(female_dir / "bd_f_1160.partsbnd.dcx", "wb") as f:
            f.write(b"FEMALE_ARMOR_PAYLOAD")

        detected = self.scanner.scan_directory(str(self.test_dir))
        skirt_set = next((s for s in detected if s.target_model_id == "1160"), None)
        self.assertIsNotNone(skirt_set)

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

        # Verify unisex in params (equipModelGender = 0: usable by both Type A and Type B)
        equip_spec = spec["equip_params"][0]
        self.assertEqual(equip_spec["field_updates"].get("equipModelGender"), 0)

        # Verify no restriction prefixes in item name or lore
        fmg_spec = spec["fmg_texts"][0]
        self.assertNotIn("[Female Only]", fmg_spec["name"])
        self.assertNotIn("[RESTRICTION: Female Only]", fmg_spec["caption"])

        # Verify AssetRenumberer stages BOTH original female part and mirrored male part
        stage_dir = self.test_dir / "stage_skirt"
        renumberer = AssetRenumberer(output_dir=str(stage_dir))
        staged = renumberer.stage_mod_set(input_base=str(self.test_dir), mod_set=skirt_set)
        self.assertEqual(len(staged), 2)
        staged_names = [Path(s).name for s in staged]
        self.assertIn("bd_f_9007.partsbnd.dcx", staged_names)
        self.assertIn("bd_m_9007.partsbnd.dcx", staged_names)
        self.assertTrue((stage_dir / "parts" / "bd_f_9007.partsbnd.dcx").exists())
        self.assertTrue((stage_dir / "parts" / "bd_m_9007.partsbnd.dcx").exists())

        # Verify PartsDeployer deploys BOTH female and mirrored male part
        deploy_dir = self.test_dir / "deploy_skirt"
        deployer = PartsDeployer()
        deployed_count = deployer.deploy_parts([skirt_set], self.test_dir, deploy_dir)
        self.assertEqual(deployed_count, 2)
        self.assertTrue((deploy_dir / "parts" / "bd_f_9007.partsbnd.dcx").exists())
        self.assertTrue((deploy_dir / "parts" / "bd_m_9007.partsbnd.dcx").exists())

        # 2. Single-gender male mod (bd_m_1570)
        male_dir = self.test_dir / "PlateArmor" / "parts"
        male_dir.mkdir(parents=True, exist_ok=True)
        with open(male_dir / "bd_m_1570.partsbnd.dcx", "wb") as f:
            f.write(b"MALE_ARMOR_PAYLOAD")

        detected = self.scanner.scan_directory(str(self.test_dir))
        plate_set = next((s for s in detected if s.target_model_id == "1570"), None)
        self.assertIsNotNone(plate_set)

        plate_set.allocation = StandaloneAllocation(
            new_model_id="9008",
            new_equip_param_id=9008000,
            new_item_lot_id=9100008,
            marker_tag="[LootForge]"
        )
        plate_spec = builder.build_patch_spec(plate_set)
        plate_equip = plate_spec["equip_params"][0]
        self.assertEqual(plate_equip["field_updates"].get("equipModelGender"), 0)

        plate_fmg = plate_spec["fmg_texts"][0]
        self.assertNotIn("[Male Only]", plate_fmg["name"])
        self.assertNotIn("[Female Only]", plate_fmg["name"])

        # Verify AssetRenumberer stages BOTH male part and mirrored female part
        stage_plate_dir = self.test_dir / "stage_plate"
        renumberer_plate = AssetRenumberer(output_dir=str(stage_plate_dir))
        staged_plate = renumberer_plate.stage_mod_set(input_base=str(self.test_dir), mod_set=plate_set)
        self.assertEqual(len(staged_plate), 2)
        staged_plate_names = [Path(s).name for s in staged_plate]
        self.assertIn("bd_m_9008.partsbnd.dcx", staged_plate_names)
        self.assertIn("bd_f_9008.partsbnd.dcx", staged_plate_names)

        # Verify PartsDeployer deploys BOTH male and mirrored female part
        deploy_plate_dir = self.test_dir / "deploy_plate"
        deployed_plate_count = deployer.deploy_parts([plate_set], self.test_dir, deploy_plate_dir)
        self.assertEqual(deployed_plate_count, 2)
        self.assertTrue((deploy_plate_dir / "parts" / "bd_m_9008.partsbnd.dcx").exists())
        self.assertTrue((deploy_plate_dir / "parts" / "bd_f_9008.partsbnd.dcx").exists())


if __name__ == "__main__":
    unittest.main()

