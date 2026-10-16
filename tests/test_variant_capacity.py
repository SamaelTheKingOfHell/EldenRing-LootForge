"""Capacity checks include source occupancy, companions, vanilla bases, and selection changes."""

from collections import Counter
import unittest

from src.diablo_generator import DiabloLootGenerator
from src.diablo_variant_builder import DiabloVariantBuilder
from src.knowledge_base import VanillaKnowledgeBase
from src.variant_capacity import calculate_capacity


def weapon_spec():
    """Small real patch-spec contract used by both planning and generation."""
    return {"set_id": "capacity_weapon", "tier": 1,
            "equip_params": [{"param_table": "EquipParamWeapon", "new_param_id": 9000000,
                              "base_clone_id": 2020000, "field_updates": {}}],
            "fmg_texts": [{"item_id": 9000000, "name": "Sword", "caption": "Lore"}],
            "loot_distribution": {"type": "enemy_drop", "target_id": "380000000", "awarded_items": [9000000]}}


class TestVariantCapacity(unittest.TestCase):
    """Prove the displayed bound with actual generator row totals."""
    def test_independent_loot_rows_cap_variants_before_equipment_overflow(self):
        capacity = calculate_capacity({"EquipParamWeapon": 10, "IndependentLootRows": 7}, [weapon_spec()], None)
        self.assertEqual(capacity.maximum, 7)
        self.assertIn("IndependentLootRows", capacity.limiting_tables)

    def test_existing_source_rows_reduce_maximum(self):
        capacity = calculate_capacity({"EquipParamWeapon": 65530}, [weapon_spec()], None)
        self.assertEqual(capacity.maximum, 5)
        self.assertEqual(capacity.generated["EquipParamWeapon"], 5)
        self.assertIn("EquipParamWeapon", capacity.limiting_tables)

    def test_vanilla_distribution_reduces_maximum(self):
        kb = VanillaKnowledgeBase({}, {})
        kb._weapons = {"2020": {"baseParamId": 2020000, "name": "Sword"}}
        # Isolate the equipment limit from the finite chest reward budget.
        kb._merchants = [{"id": "shop_fixture", "name": "Test merchant", "progressionTier": tier}
                         for tier in (1, 2)]
        plain = calculate_capacity({"EquipParamWeapon": 65525}, [weapon_spec()], kb)
        vanilla = calculate_capacity({"EquipParamWeapon": 65525}, [weapon_spec()], kb, include_vanilla=True)
        self.assertEqual(plain.maximum, 10)
        self.assertEqual(vanilla.maximum, 5)

    def test_companions_are_counted_with_the_real_destination_planner(self):
        kb = VanillaKnowledgeBase.from_data_dir("data")
        spec = weapon_spec()
        planned = DiabloVariantBuilder.generate_variants(DiabloLootGenerator(seed=7, knowledge_base=kb),
                                                          spec, 20, kb, count_only=True)
        actual = DiabloVariantBuilder.generate_variants(DiabloLootGenerator(seed=7, knowledge_base=kb), spec, 20, kb)
        counts = Counter(row["param_table"] for variant in actual for row in variant["equip_params"])
        self.assertEqual(planned, dict(counts))
        self.assertLessEqual(counts["EquipParamAccessory"], 20)
        capacity = calculate_capacity({"EquipParamAccessory": 65530}, [spec], kb, ceiling=20)
        self.assertLessEqual(capacity.maximum, 20)
        self.assertLessEqual(capacity.existing["EquipParamAccessory"] + capacity.generated.get("EquipParamAccessory", 0), 65535)

    def test_full_source_disables_impossible_selection(self):
        capacity = calculate_capacity({"EquipParamWeapon": 65535}, [weapon_spec()], None)
        self.assertEqual(capacity.maximum, 0)

    def test_live_original_rewards_reduce_selection_capacity(self):
        from src.knowledge_loader import KnowledgeLoader
        models, routes = {}, {}
        KnowledgeLoader.ingest_discovered_snapshot({"SchemaVersion": 3, "BossLots": [{
            "LotId": 10000, "Name": "Boss", "Tier": 1, "FreeRows": 8, "OriginalRewards": 2}]}, models, routes)
        kb = VanillaKnowledgeBase(models, routes)
        capacity = calculate_capacity({}, [weapon_spec()], kb, ceiling=20)
        self.assertEqual(capacity.maximum, 2)
        self.assertEqual(capacity.generated, {"EquipParamWeapon": 2})
        self.assertIn("LootDestinations", capacity.limiting_tables)

    def test_vanilla_param_only_items_do_not_exhaust_model_namespace(self):
        from src.id_allocator import IdAllocator
        allocator = IdAllocator(min_model_id=9000, max_model_id=9000)
        allocator.allocate("replacement")
        for index in range(1100):
            allocator.allocate_virtual(f"vanilla-{index}")
        self.assertEqual(allocator.allocate("replacement").new_model_id, "9000")
