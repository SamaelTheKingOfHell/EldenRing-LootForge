"""
Parameter builder test suite.

Validates that parameter patch specifications and FMG localization rows are correctly generated
for both Boss Soul Remembrances and enemy mob drop tables.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import (
    DetectedModSet, ModPartFile, EquipmentSlot,
    StandaloneAllocation, LootTarget, LootDistributionType
)
from src.param_builder import ParamBuilder


class TestParamBuilder(unittest.TestCase):
    """
    Validates parameter patch record structure and FMG text generation.
    """

    def setUp(self):
        self.builder = ParamBuilder()

    def test_boss_remembrance_patch_spec(self):
        """Verifies EquipParam rows and ShopLineup routing for Boss Remembrances."""
        mod_set = DetectedModSet(
            set_id="radahn_berserk",
            folder_or_archive_name="RadahnBerserk",
            target_model_id="4200",
            target_vanilla_name="Radahn's Lion Set",
            parts=[
                ModPartFile("am_m_4200.partsbnd.dcx", "parts/am_m_4200.partsbnd.dcx", EquipmentSlot.ARMS, "4200"),
                ModPartFile("bd_m_4200.partsbnd.dcx", "parts/bd_m_4200.partsbnd.dcx", EquipmentSlot.BODY, "4200"),
            ],
            allocation=StandaloneAllocation(
                new_model_id="9001",
                new_equip_param_id=9001000,
                new_item_lot_id=9100001,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.BOSS_REMEMBRANCE,
                target_id="remembrance_starscourge",
                display_name="Remembrance of the Starscourge (General Radahn)",
                chance_or_cost=40000
            )
        )

        spec = self.builder.build_patch_spec(mod_set)
        self.assertEqual(len(spec["equip_params"]), 2)
        self.assertEqual(len(spec["fmg_texts"]), 2)

        # Check body armor model ID binding
        body_param = next(p for p in spec["equip_params"] if "Body" in p["row_name"])
        self.assertEqual(body_param["field_updates"]["bodyEquipModelId"], 9001)

        # Check loot spec
        loot = spec["loot_distribution"]
        self.assertEqual(loot["type"], "shop_lineup")
        self.assertEqual(loot["shop_type"], "finger_reader_enia")
        self.assertEqual(loot["cost_or_remembrance"], 40000)

    def test_enemy_drop_patch_spec(self):
        """Verifies ItemLotParam drop rate configuration for enemy drops."""
        mod_set = DetectedModSet(
            set_id="cleanrot_variant",
            folder_or_archive_name="CleanrotVariant",
            target_model_id="4110",
            target_vanilla_name="Cleanrot Knight Set",
            parts=[
                ModPartFile("hd_m_4110.partsbnd.dcx", "parts/hd_m_4110.partsbnd.dcx", EquipmentSlot.HEAD, "4110")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9002",
                new_equip_param_id=9002000,
                new_item_lot_id=9100002,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="cleanrot_knight",
                display_name="Cleanrot Knight",
                chance_or_cost=15.0
            )
        )

        spec = self.builder.build_patch_spec(mod_set)
        loot = spec["loot_distribution"]
        self.assertEqual(loot["type"], "enemy_drop")
        self.assertEqual(loot["lot_id"], 9100002)
        self.assertEqual(loot["drop_rate_percent"], 15.0)

    def test_enemy_drop_patch_spec_with_knowledge_base(self):
        """Verifies ItemLotParam resolves authentic enemy lotParamId when KB is supplied."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir(str(Path(__file__).resolve().parent.parent / "data"))
        builder_with_kb = ParamBuilder(kb)

        mod_set = DetectedModSet(
            set_id="cleanrot_variant",
            folder_or_archive_name="CleanrotVariant",
            target_model_id="4110",
            target_vanilla_name="Cleanrot Knight Set",
            parts=[
                ModPartFile("hd_m_4110.partsbnd.dcx", "parts/hd_m_4110.partsbnd.dcx", EquipmentSlot.HEAD, "4110")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9002",
                new_equip_param_id=9002000,
                new_item_lot_id=9100002,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="cleanrot_knight",
                display_name="Cleanrot Knight",
                chance_or_cost=15.0
            )
        )

        spec = builder_with_kb.build_patch_spec(mod_set)
        loot = spec["loot_distribution"]
        self.assertEqual(loot["type"], "enemy_drop")
        self.assertEqual(loot["lot_id"], 380000000)  # Authentic Cleanrot Knight lot ID!

    def test_uchigatana_weapon_cloning_resolves_correct_katana_id(self):
        """Verifies that Uchigatana (model 9000) clones from 9000000 (Katana), NOT 90000000 (Knife)."""
        mod_set = DetectedModSet(
            set_id="mod_uchigatana",
            folder_or_archive_name="CustomUchigatana",
            target_model_id="9000",
            target_vanilla_name="Uchigatana",
            is_weapon=True,
            parts=[
                ModPartFile("wp_a_9000.partsbnd.dcx", "parts/wp_a_9000.partsbnd.dcx", EquipmentSlot.WEAPON, "9000")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9005",
                new_equip_param_id=9005000,
                new_item_lot_id=9100005,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="godrick_soldier",
                display_name="Godrick Soldier",
                chance_or_cost=25.0
            )
        )

        spec = self.builder.build_patch_spec(mod_set)
        wep_param = spec["equip_params"][0]
        self.assertEqual(wep_param["param_table"], "EquipParamWeapon")
        # Must be 9000000 (Uchigatana Katana), NEVER 90000000 (Knife/Cirque)!
        self.assertEqual(wep_param["base_clone_id"], 9000000)

    def test_weapon_build_patch_spec_with_knowledge_base_no_unbound_local_error(self):
        """Verifies build_patch_spec for weapons with knowledge base populated executes without UnboundLocalError on vanilla_offset."""
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase.from_data_dir("data")
        builder_with_kb = ParamBuilder(knowledge_base=kb)

        mod_set = DetectedModSet(
            set_id="mod_uchigatana_kb",
            folder_or_archive_name="CustomUchigatana",
            target_model_id="9000",
            target_vanilla_name="Uchigatana",
            is_weapon=True,
            parts=[
                ModPartFile("wp_a_9000.partsbnd.dcx", "parts/wp_a_9000.partsbnd.dcx", EquipmentSlot.WEAPON, "9000")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9006",
                new_equip_param_id=9006000,
                new_item_lot_id=9100006,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.ENEMY_DROP,
                target_id="godrick_soldier",
                display_name="Godrick Soldier",
                chance_or_cost=25.0
            )
        )

        spec = builder_with_kb.build_patch_spec(mod_set)
        self.assertIsNotNone(spec)
        wep_param = spec["equip_params"][0]
        self.assertEqual(wep_param["slot_offset"], 0)
        self.assertEqual(wep_param["base_clone_id"], 9000000)
        fmg = spec["fmg_texts"][0]
        self.assertEqual(fmg["slot_offset"], 0)


if __name__ == "__main__":
    unittest.main()

