"""Regression cases for pickup floods, lost armor pieces and equipment identity."""
import copy
import unittest
from src.diablo_generator import DiabloLootGenerator
from src.diablo_destinations import choose_destination, DestinationCapacityError
from src.models import ProgressionTier


class LootRuntimeRoutes(unittest.TestCase):
    def test_weapon_reinforcement_and_accessory_namespaces_do_not_alias(self):
        generator = DiabloLootGenerator(seed=0)
        ids = [generator.allocate_variant_id() for _ in range(1200)]
        accessories = [generator.allocate_variant_id(is_accessory=True) for _ in range(100)]
        self.assertEqual(len(set(item-item % 100 for item in ids)), len(ids))
        self.assertTrue(all(item % 100 == 0 for item in ids))
        self.assertTrue(all(20000 <= item < 60000 for item in accessories))
        self.assertFalse(set(ids) & set(accessories))

    def test_full_armor_moves_as_one_group_without_overflow_into_resources(self):
        gen = DiabloLootGenerator(seed=0)
        small = {'id': 'chest_small', 'lotParamId': 10000, 'name': 'Small chest', 'freeRows': 2}
        large = {'id': 'chest_large', 'lotParamId': 20000, 'name': 'Large chest', 'freeRows': 5}
        pools = (None, None, None, [], [small, large], [], [], None, None)
        spec = {'set_id': 'armor', 'equip_params': [{}, {}, {}, {}]}
        loot, *_ = choose_destination(gen, pools, spec, 1, ProgressionTier.EARLY)
        self.assertEqual(loot['target_id'], '20000')
        with self.assertRaises(DestinationCapacityError):
            choose_destination(gen, pools, spec, 1, ProgressionTier.EARLY)

    def test_exhausted_vendor_is_not_silently_redirected_to_another_table(self):
        gen = DiabloLootGenerator(seed=0)
        merchant = {'id': 'shop_100500', 'name': 'Kale', 'rangeStart': 100500, 'rangeEnd': 100524, 'freeRows': 1}
        pools = (None, None, None, [], [], [merchant], [], None, None)
        spec = {'set_id': 'sword', 'equip_params': [{}]}
        loot, *_ = choose_destination(gen, pools, spec, 2, ProgressionTier.EARLY)
        self.assertEqual(loot['range_start'], 100500)
        with self.assertRaises(DestinationCapacityError):
            choose_destination(gen, pools, spec, 2, ProgressionTier.EARLY)

    def test_explicit_caller_route_is_not_mutated(self):
        spec = {'set_id': 'sword', 'equip_params': [{}], 'loot_distribution': {'type': 'enemy_drop', 'awarded_items': [9]}}
        original = copy.deepcopy(spec)
        loot, *_ = choose_destination(DiabloLootGenerator(seed=0), (None, None, None, [], [], [], [], None, None), spec, 0, 1)
        loot['awarded_items'].append(10)
        self.assertEqual(spec, original)
