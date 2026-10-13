"""
Verification script for LootForge small corrections branch.
Verifies:
1. Authentic vanilla IDs and full starting gear coverage.
2. Passive effects UI routing (spEffectMsgId0..2, spEffectBehaviorId0..2, residentSpEffectId..2).
3. Non-destructive loot injection behavior.
"""

import sys
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.knowledge_base import VanillaKnowledgeBase
from src.diablo_generator import DiabloLootGenerator
from src.diablo_affixes import AFFIX_POOL


class TestSmallCorrectionsVerification(unittest.TestCase):
    def setUp(self):
        self.kb = VanillaKnowledgeBase.from_data_dir(str(repo_root / "data"))
        self.generator = DiabloLootGenerator(seed=999)

    def test_correction_1_starting_gear_authentic_ids(self):
        """Correction 1: All 10 starting classes have weapons, shields, and armors cataloged."""
        specs = self.generator.generate_vanilla_stat_injections(knowledge_base=self.kb)
        injected_ids = {s["equip_params"][0]["new_param_id"] for s in specs}

        # Verify all 10 starting classes' weapons & shields
        expected_weapons = {
            2000000: "Vagabond Longsword",
            18000000: "Vagabond Halberd",
            31330000: "Vagabond Heater Shield",
            7140000: "Warrior Scimitar",
            30090000: "Warrior Riveted Wooden Shield",
            14000000: "Hero Battle Axe",
            31230000: "Hero Large Leather Shield",
            1090000: "Bandit Great Knife",
            40000000: "Bandit Shortbow",
            30000000: "Bandit Buckler",
            33130000: "Astrologer's Staff",
            2010000: "Astrologer Short Sword",
            30080000: "Astrologer Scripture Wooden Shield",
            16000000: "Prophet Short Spear",
            34000000: "Prophet/Confessor Finger Seal",
            30030000: "Prophet Rickety Shield",
            9000000: "Samurai Uchigatana",
            41000000: "Samurai Longbow",
            30070000: "Samurai Red Thorn Roundshield",
            5000000: "Prisoner Estoc",
            33000000: "Prisoner Glintstone Staff",
            30110000: "Prisoner Rift Shield",
            2020000: "Confessor Broadsword",
            31100000: "Confessor Blue-Gold Kite Shield",
            11010000: "Wretch Club"
        }

        for w_id, name in expected_weapons.items():
            self.assertIn(w_id, injected_ids, f"Starting gear {name} (ID: {w_id}) must be in vanilla stat injections!")

        # Verify starting armor sets
        expected_armors = {
            660000: "Vagabond Knight Helm",
            660100: "Vagabond Knight Armor",
            870000: "Land of Reeds Helm",
            870100: "Land of Reeds Armor",
            630000: "Astrologer Hood",
            630100: "Astrologer Robe",
            730000: "Champion Headband",
            730100: "Champion Pauldron",
            1401000: "Bandit Mask",
            931100: "Bandit Garb",
            670000: "Blue Cloth Cowl",
            670100: "Blue Cloth Vest",
            880000: "Confessor Hood",
            880100: "Confessor Armor",
            890000: "Prisoner Iron Mask",
            890100: "Prisoner Clothing",
            620000: "Prophet Blindfold",
            622100: "Prophet Robe"
        }

        for a_id, name in expected_armors.items():
            self.assertIn(a_id, injected_ids, f"Starting armor piece {name} (ID: {a_id}) must be in vanilla stat injections!")

    def test_correction_2_passive_ui_slots_and_buildups(self):
        """Correction 2: Passive affixes properly populate UI message IDs and game engine effect slots."""
        # Check Glacial (Frostbite)
        glacial = next(a for a in AFFIX_POOL if a.name == "Glacial")
        self.assertTrue(glacial.is_on_hit_effect)
        self.assertEqual(glacial.sp_effect_msg_id, 6601, "Glacial must reference WeaponEffect.fmg 6601")
        self.assertEqual(glacial.sp_effect_id, 6702, "Glacial must reference SpEffect 6702 (Frostbite)")

        # Check Serrated (Bleed)
        serrated = next(a for a in AFFIX_POOL if a.name == "Serrated")
        self.assertTrue(serrated.is_on_hit_effect)
        self.assertEqual(serrated.sp_effect_msg_id, 6501, "Serrated must reference WeaponEffect.fmg 6501")
        self.assertEqual(serrated.sp_effect_id, 6400, "Serrated must reference SpEffect 6400 (Blood loss)")

        # Check routing
        updates = {}
        DiabloLootGenerator.apply_affixes_to_equipment(updates, [glacial, serrated], is_weapon=True)
        self.assertEqual(updates["spEffectBehaviorId0"], 6702)
        self.assertEqual(updates["spEffectMsgId0"], 6601)
        self.assertEqual(updates["spEffectBehaviorId1"], 6400)
        self.assertEqual(updates["spEffectMsgId1"], 6501)

    def test_correction_3_major_iconic_weapon_ids(self):
        """Correction 3: Major iconic weapons use authentic Elden Ring IDs (not manufactured IDs)."""
        weapons = self.kb.list_all_vanilla_weapons()
        model_to_base_id = {m: w["baseParamId"] for m, w in weapons.items()}

        self.assertEqual(model_to_base_id.get("0206"), 4000000, "Greatsword must be 4000000 (not 2060000)")
        self.assertEqual(model_to_base_id.get("0211"), 3090000, "Dark Moon Greatsword must be 3090000 (not 2110000)")
        self.assertEqual(model_to_base_id.get("0415"), 9060000, "Moonveil must be 9060000 (not 4150000)")
        self.assertEqual(model_to_base_id.get("0416"), 9040000, "Rivers of Blood must be 9040000 (not 4160000)")
        self.assertEqual(model_to_base_id.get("0617"), 2180000, "Carian Knight's Sword must be 2180000 (not 6170000)")
        self.assertEqual(model_to_base_id.get("0606"), 3080000, "Banished Knight's GS must be 3080000 (not 6060000)")
        self.assertEqual(model_to_base_id.get("0556"), 10050000, "Eleonora's Poleblade must be 10050000 (not 5560000)")

    def test_correction_4_accessories_in_loot_pool(self):
        """Correction 4: Accessories/talismans have authentic retail IDs, affixes, and stat infusions."""
        accessories = self.kb.list_all_vanilla_accessories()
        self.assertGreaterEqual(len(accessories), 25, "Must have authentic accessories loaded in knowledge base!")

        model_to_base_id = {m: a["baseParamId"] for m, a in accessories.items()}
        self.assertEqual(model_to_base_id.get("1000"), 1000, "Crimson Amber Medallion must be ID 1000")
        self.assertEqual(model_to_base_id.get("1010"), 1010, "Erdtree's Favor must be ID 1010")
        self.assertEqual(model_to_base_id.get("1051"), 1051, "Radagon's Soreseal must be ID 1051")
        self.assertEqual(model_to_base_id.get("1110"), 1110, "Gold Scarab must be ID 1110")
        self.assertEqual(model_to_base_id.get("3090"), 3090, "Godfrey Icon must be ID 3090")

        # Test stat infusion generation
        specs = self.generator.generate_vanilla_stat_injections(knowledge_base=self.kb)
        acc_specs = [s for s in specs if s["equip_params"][0].get("param_table") == "EquipParamAccessory"]
        self.assertGreaterEqual(len(acc_specs), 20, "Must generate stat injections for accessories!")

        # Test accessory affix rolling and effect mapping
        affs = self.generator.roll_affixes(
            from_rarity=None, is_weapon=False, is_accessory=True
        ) if hasattr(self.generator, "from_rarity") else self.generator.roll_affixes(
            from_rarity if False else 4, is_weapon=False, is_accessory=True
        )
        # Note: generator.roll_affixes(RarityTier.LEGENDARY, is_weapon=False, is_accessory=True)
        from src.diablo_affixes import RarityTier
        leg_affs = self.generator.roll_affixes(RarityTier.LEGENDARY, is_weapon=False, is_accessory=True)
        self.assertGreaterEqual(len(leg_affs), 2)
        updates = {}
        DiabloLootGenerator.apply_affixes_to_equipment(updates, leg_affs, is_weapon=False, is_accessory=True)
        has_resident = any(k.startswith("residentSpEffectId") for k in updates) or "refId" in updates
        self.assertTrue(has_resident, "Accessory updates must populate residentSpEffects or refId!")

    def test_correction_5_rotation_bosses_chests_rest_and_multi_drop(self):
        """Correction 5: Rotation sequence follows bosses > chests > the rest with multi-drops."""
        from src.models import (
            DetectedModSet, ModPartFile, EquipmentSlot, StandaloneAllocation,
            LootTarget, LootDistributionType
        )
        from src.param_builder import ParamBuilder

        builder = ParamBuilder(knowledge_base=self.kb)
        test_set = DetectedModSet(
            set_id="TestArmor_1500",
            folder_or_archive_name="Test Armor",
            target_model_id="1500",
            target_vanilla_name="Knight Helm",
            parts=[ModPartFile("hr_m_1500.partsbnd.dcx", "hr_m_1500.partsbnd.dcx", EquipmentSlot.HEAD, "1500", "m", 100)],
            allocation=StandaloneAllocation(
                new_model_id="9020",
                new_equip_param_id=9020000,
                new_item_lot_id=9100020,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="431100000",
                display_name="Godrick Soldier",
                chance_or_cost=100.0
            )
        )

        base_spec = builder.build_patch_spec(test_set)
        variants = self.generator.generate_variants_for_spec(
            base_spec=base_spec,
            variants_per_item=6,
            knowledge_base=self.kb
        )
        self.assertEqual(len(variants), 6)

        # Mod buckets: 0=Boss, 1=Chest, 2=Rest, 3=Boss, 4=Chest, 5=Rest
        for idx, var in enumerate(variants):
            bucket = idx % 3
            loot = var.get("loot_distribution", {})
            awarded = loot.get("awarded_items", [])
            if bucket == 0:
                # Boss: multi-drop (bundled companion accessory)
                self.assertEqual(len(awarded), 2, f"Boss variant at index {idx} must award multiple items!")
                tables = [ep["param_table"] for ep in var["equip_params"]]
                self.assertIn("EquipParamAccessory", tables)
            elif bucket == 1:
                # Chest: multi-drop (bundled companion accessory)
                self.assertEqual(len(awarded), 2, f"Chest variant at index {idx} must award multiple items!")
                tables = [ep["param_table"] for ep in var["equip_params"]]
                self.assertIn("EquipParamAccessory", tables)
            elif bucket == 2:
                # Rest: single drop
                self.assertEqual(len(awarded), 1, f"Rest variant at index {idx} must award single item!")


if __name__ == "__main__":
    unittest.main()
