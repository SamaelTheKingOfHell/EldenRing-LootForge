"""
Accessory and Talisman modular injection tests.

Verifies:
1. Authentic talisman iconId extraction and propagation (>= 18000).
2. Elimination of placeholder/transparent icons (iconId 1000).
3. Parity of FMG text specs across companion and standalone accessories.
Adheres to [CS-MODULAR] and [CS-GRANULARITY].
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.knowledge_base import VanillaKnowledgeBase, ProgressionTier
from src.diablo_variant_builder import DiabloVariantBuilder
from src.param_builder import ParamBuilder
from src.models import DetectedModSet, ModPartFile, EquipmentSlot, StandaloneAllocation, LootTarget, LootDistributionType


class TestAccessoryModularInjection(unittest.TestCase):
    """Validates accessory iconId integrity and FMG accessory flags."""

    def setUp(self):
        self.mock_accs = {
            "1000": {
                "name": "Crimson Amber Medallion",
                "baseParamId": 1000,
                "iconId": 18000,
                "progressionTier": 1
            },
            "1020": {
                "name": "Viridian Amber Medallion",
                "baseParamId": 1020,
                "iconId": 18020,
                "progressionTier": 1
            }
        }
        self.kb = VanillaKnowledgeBase({}, {})
        self.kb._accessories = dict(self.mock_accs)
        self.kb._weapons = {}
        self.kb._protectors = {}

    def test_discovered_accessory_icon_id_ingestion(self):
        """Verifies snapshot ingestion captures IconId with authentic 18000 fallback."""
        from src.knowledge_loader import KnowledgeLoader

        mock_snap = {
            "Accessories": [
                {"Id": 1000, "Name": "Crimson Amber Medallion", "SortId": 10, "RefId": 3100, "IconId": 18000, "Tier": 1},
                {"Id": 1050, "Name": "Arsenal Charm", "SortId": 20, "RefId": 3105, "IconId": 18050, "Tier": 1},
                {"Id": 1090, "Name": "Missing Icon Talisman", "SortId": 30, "RefId": 3109, "Tier": 1}
            ],
            "Weapons": [],
            "Protectors": [],
            "BossLots": [],
            "Chests": []
        }

        models_data = {}
        routes_data = {}
        KnowledgeLoader.ingest_discovered_snapshot(mock_snap, models_data, routes_data)

        disc = models_data.get("_discovered_accessories", {})
        self.assertIn("1000", disc)
        self.assertEqual(disc["1000"]["iconId"], 18000)
        self.assertIn("1050", disc)
        self.assertEqual(disc["1050"]["iconId"], 18050)
        # Verify fallback is authentic 18000, NOT non-existent 1000
        self.assertIn("1090", disc)
        self.assertEqual(disc["1090"]["iconId"], 18000)

    def test_diablo_companion_accessory_icon_id(self):
        """Verifies DiabloVariantBuilder assigns valid authentic iconId (>= 18000) to companion accessories."""
        from src.diablo_generator import DiabloLootGenerator
        mock_generator = DiabloLootGenerator(seed=42, knowledge_base=self.kb)

        base_spec = {
            "set_id": "test_boss_set",
            "equip_params": [{
                "param_table": "EquipParamProtector",
                "new_param_id": 9000100,
                "base_clone_id": 40100,
                "slot_offset": 100,
                "field_updates": {}
            }],
            "fmg_texts": [{
                "item_id": 9000100,
                "name": "Boss Armor",
                "caption": "Armor",
                "info": "Info"
            }],
            "loot_distribution": {
                "type": "chest_drop",
                "lot_id": 100500,
                "target_id": "100500"
            }
        }

        variants = DiabloVariantBuilder.generate_variants(
            generator=mock_generator,
            base_spec=base_spec,
            variants_per_item=2,
            knowledge_base=self.kb
        )
        self.assertEqual(len(variants), 2)

        v_spec = variants[0]
        acc_params = [p for p in v_spec["equip_params"] if p["param_table"] == "EquipParamAccessory"]
        self.assertTrue(len(acc_params) >= 1)

        for acc in acc_params:
            self.assertIn("iconId", acc["field_updates"])
            self.assertGreaterEqual(acc["field_updates"]["iconId"], 18000)

        # Check FMG texts have is_accessory == True
        acc_fmgs = [f for f in v_spec["fmg_texts"] if f.get("is_accessory")]
        self.assertTrue(len(acc_fmgs) >= 1)

    def test_param_builder_chest_accessory_icon_id(self):
        """Verifies ParamBuilder assigns authentic iconId >= 18000 to chest-injected accessories."""
        builder = ParamBuilder(knowledge_base=self.kb)

        mod_set = DetectedModSet(
            set_id="chest_talisman_test",
            folder_or_archive_name="ChestTalismanTest",
            target_model_id="4000",
            target_vanilla_name="Carian Knight Set",
            parts=[
                ModPartFile("am_m_4000.partsbnd.dcx", "parts/am.dcx", EquipmentSlot.ARMS, "4000")
            ],
            allocation=StandaloneAllocation(
                new_model_id="9050",
                new_equip_param_id=9050000,
                new_item_lot_id=9150000,
                marker_tag="[LootForge]"
            ),
            loot_target=LootTarget(
                route_type=LootDistributionType.MAP_PICKUP,
                target_id="100500",
                display_name="Waypoint Ruins Chest",
                chance_or_cost=100.0
            )
        )

        spec = builder.build_patch_spec(mod_set)
        acc_params = [p for p in spec["equip_params"] if p["param_table"] == "EquipParamAccessory"]
        self.assertEqual(len(acc_params), 2)

        for acc in acc_params:
            self.assertIn("iconId", acc["field_updates"])
            self.assertGreaterEqual(acc["field_updates"]["iconId"], 18000)


if __name__ == "__main__":
    unittest.main()
