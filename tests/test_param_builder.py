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
                marker_tag="✦ [LootForge]"
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
                marker_tag="✦ [LootForge]"
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


if __name__ == "__main__":
    unittest.main()
