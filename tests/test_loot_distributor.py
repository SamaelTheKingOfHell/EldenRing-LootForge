"""
Test suite for LootDistributor adhering to [CS-NO-MOCK].

Validates AdditionType, AntiDup (Boss Rotation and Everything in the Wild),
set cohesion invariance, rate calculation, and color status.
"""

import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.knowledge_base import VanillaKnowledgeBase
from src.loot_distributor import LootDistributor
from src.models import (
    AdditionType, AntiDup, DetectedModSet, ModPartFile, EquipmentSlot,
    LootDistributionType
)


class TestLootDistributor(unittest.TestCase):
    """
    Validates distribution rules, Enums, and rate calculations.
    """

    def setUp(self):
        self.kb = VanillaKnowledgeBase.from_data_dir(str(BASE_DIR / "data"))
        self.distributor = LootDistributor(self.kb)

    def test_set_invariance_single_target(self):
        """Verifies that all pieces of a multi-part set share a single loot target."""
        mod_set = DetectedModSet(
            set_id="carian_mod",
            folder_or_archive_name="CarianMod",
            target_model_id="4000",
            target_vanilla_name="Carian Knight Set",
            parts=[
                ModPartFile("am_m_4000.partsbnd.dcx", "parts/am_m_4000.partsbnd.dcx", EquipmentSlot.ARMS, "4000"),
                ModPartFile("bd_m_4000.partsbnd.dcx", "parts/bd_m_4000.partsbnd.dcx", EquipmentSlot.BODY, "4000"),
                ModPartFile("hd_m_4000.partsbnd.dcx", "parts/hd_m_4000.partsbnd.dcx", EquipmentSlot.HEAD, "4000"),
                ModPartFile("lg_m_4000.partsbnd.dcx", "parts/lg_m_4000.partsbnd.dcx", EquipmentSlot.LEGS, "4000"),
            ]
        )

        target = self.distributor.distribute_set(
            mod_set,
            addition_type=AdditionType.STANDARD_ADDITION,
            anti_dup=AntiDup.BOSS_ROTATION
        )

        self.assertIsNotNone(target)
        self.assertEqual(mod_set.loot_target, target)
        self.assertTrue(len(target.display_name) > 0)

    def test_anti_dup_boss_rotation_different_boss(self):
        """Verifies that 100% boss drops are rotated to a different boss."""
        mod_set = DetectedModSet(
            set_id="radahn_variant",
            folder_or_archive_name="RadahnVariant",
            target_model_id="4200",  # General Radahn
            target_vanilla_name="Radahn's Lion Set",
            parts=[
                ModPartFile("bd_m_4200.partsbnd.dcx", "parts/bd_m_4200.partsbnd.dcx", EquipmentSlot.BODY, "4200")
            ]
        )

        target = self.distributor.distribute_set(
            mod_set,
            addition_type=AdditionType.STANDARD_ADDITION,
            anti_dup=AntiDup.BOSS_ROTATION
        )

        # Must not be the original Radahn boss remembrance
        self.assertNotEqual(target.target_id, "remembrance_starscourge")
        self.assertEqual(target.route_type, LootDistributionType.BOSS_REMEMBRANCE)

    def test_anti_dup_everything_in_the_wild(self):
        """Verifies that EVERYTHING_IN_THE_WILD routes boss gear into normal mob drops."""
        mod_set = DetectedModSet(
            set_id="malenia_variant",
            folder_or_archive_name="MaleniaVariant",
            target_model_id="4230",  # Malenia
            target_vanilla_name="Malenia's Set",
            parts=[
                ModPartFile("bd_m_4230.partsbnd.dcx", "parts/bd_m_4230.partsbnd.dcx", EquipmentSlot.BODY, "4230")
            ]
        )

        target = self.distributor.distribute_set(
            mod_set,
            addition_type=AdditionType.STANDARD_ADDITION,
            anti_dup=AntiDup.EVERYTHING_IN_THE_WILD
        )

        self.assertEqual(target.route_type, LootDistributionType.ENEMY_DROP)

    def test_random_addition_non_dropped_vs_dropped(self):
        """Verifies non-dropped items stay in bosses/shops/transfusions in random mode."""
        # Non-dropped item (Knight Set: bought at Twin Maiden Husks)
        shop_set = DetectedModSet(
            set_id="knight_set",
            folder_or_archive_name="KnightSet",
            target_model_id="4030",
            target_vanilla_name="Knight Set",
            parts=[ModPartFile("bd_m_4030.partsbnd.dcx", "bd_m_4030.partsbnd.dcx", EquipmentSlot.BODY, "4030")]
        )
        target_shop = self.distributor.distribute_set(shop_set, addition_type=AdditionType.RANDOM_ADDITION)
        self.assertIn(target_shop.route_type, [LootDistributionType.BOSS_REMEMBRANCE, LootDistributionType.MERCHANT_SHOP])

        # Dropped item (Cleanrot Knight set: drops from cleanrot mobs)
        mob_set = DetectedModSet(
            set_id="cleanrot_set",
            folder_or_archive_name="CleanrotSet",
            target_model_id="4110",
            target_vanilla_name="Cleanrot Knight Set",
            parts=[ModPartFile("bd_m_4110.partsbnd.dcx", "bd_m_4110.partsbnd.dcx", EquipmentSlot.BODY, "4110")]
        )
        target_mob = self.distributor.distribute_set(mob_set, addition_type=AdditionType.RANDOM_ADDITION)
        self.assertEqual(target_mob.route_type, LootDistributionType.ENEMY_DROP)

    def test_rate_calculation_and_colors(self):
        """Verifies final rate math and color coding (green/red/grey)."""
        vanilla = 20.0

        # Baseline 100% -> Equal -> grey
        final_100 = self.distributor.calculate_final_rate(20.0, 100.0)
        self.assertEqual(final_100, 20.0)
        self.assertEqual(self.distributor.get_rate_color_status(final_100, vanilla), "grey")

        # Higher rate -> green
        final_high = self.distributor.calculate_final_rate(20.0, 150.0)
        self.assertEqual(final_high, 30.0)
        self.assertEqual(self.distributor.get_rate_color_status(final_high, vanilla), "green")

        # Lower rate -> red
        final_low = self.distributor.calculate_final_rate(20.0, 50.0)
        self.assertEqual(final_low, 10.0)
        self.assertEqual(self.distributor.get_rate_color_status(final_low, vanilla), "red")

    def test_addition_type_test_mode_cycles_all_pools(self):
        """Verifies that AdditionType.TEST_MODE cycles items across Bosses, Mobs, and Shops."""
        self.distributor.reset_rotation_state()
        sets = [
            DetectedModSet(
                set_id=f"test_set_{i}",
                folder_or_archive_name=f"Set{i}",
                target_model_id="4000",
                target_vanilla_name="Carian Knight Set",
                parts=[ModPartFile(f"bd_m_4000_{i}.dcx", "p", EquipmentSlot.BODY, "4000")]
            )
            for i in range(6)
        ]

        targets = [
            self.distributor.distribute_set(s, addition_type=AdditionType.TEST_MODE)
            for s in sets
        ]

        # Targets should cycle: Boss -> Enemy -> Merchant -> Boss -> Enemy -> Merchant
        self.assertEqual(targets[0].route_type, LootDistributionType.BOSS_REMEMBRANCE)
        self.assertEqual(targets[1].route_type, LootDistributionType.ENEMY_DROP)
        self.assertEqual(targets[2].route_type, LootDistributionType.MERCHANT_SHOP)
        self.assertEqual(targets[3].route_type, LootDistributionType.BOSS_REMEMBRANCE)
        self.assertEqual(targets[4].route_type, LootDistributionType.ENEMY_DROP)
        self.assertEqual(targets[5].route_type, LootDistributionType.MERCHANT_SHOP)

        # Enemy drop in test mode should have 100% drop rate for guaranteed in-game verification
        self.assertEqual(targets[1].chance_or_cost, 100.0)


if __name__ == "__main__":
    unittest.main()
