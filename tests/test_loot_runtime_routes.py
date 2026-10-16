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
        # Four armor pieces plus an original chest reward would exceed four items.
        pools = (None, None, None, [], [small, large], [], [dict(large, name='Gear enemy')], None, None)
        spec = {'set_id': 'armor', 'equip_params': [{}, {}, {}, {}]}
        loot, *_ = choose_destination(gen, pools, spec, 1, ProgressionTier.EARLY)
        self.assertEqual(loot['target_id'], '20000')
        self.assertEqual(loot['type'], 'enemy_drop')
        with self.assertRaises(DestinationCapacityError):
            choose_destination(gen, pools, spec, 1, ProgressionTier.EARLY)

    def test_separate_sets_boss_chest_aliases_and_bonus_share_four_item_budget(self):
        gen = DiabloLootGenerator(seed=0)
        boss = {'lotParamId': 10000, 'name': 'Boss', 'freeRows': 8, 'originalRewards': 2}
        chest = dict(boss, lotParamId=10001, name='Chest alias')
        pools = (None, None, None, [boss], [chest], [], [], None, [{'id': 1000}])
        total = 2
        for index in range(2):
            result = choose_destination(gen, pools, {'set_id': f'weapon-{index}', 'equip_params': [{}]}, index, 1)
            total += 1 + result[-1]
            if total == 4:
                break
        self.assertEqual(total, 4)
        with self.assertRaises(DestinationCapacityError):
            choose_destination(gen, pools, {'set_id': 'extra', 'equip_params': [{}]}, 0, 1)

    def test_optional_talisman_is_omitted_when_equipment_fills_budget(self):
        from src.diablo_destinations import companion_count
        gen = DiabloLootGenerator(seed=0)
        spec = {'set_id': 'three-pieces', 'equip_params': [{}, {}, {}]}
        index = next(i for i in range(1000) if companion_count(gen, spec, i, True))
        record = {'lotParamId': 10000, 'name': 'Chest', 'freeRows': 9, 'originalRewards': 1}
        result = choose_destination(gen, (None, None, None, [], [record], [], [], None, [{}]), spec, index, 1)
        self.assertEqual(result[-1], 0)

    def test_existing_large_original_reward_is_preserved_and_receives_no_bonus(self):
        record = {'lotParamId': 10000, 'name': 'Host reward', 'freeRows': 5, 'originalRewards': 5}
        with self.assertRaises(DestinationCapacityError):
            choose_destination(DiabloLootGenerator(seed=0), (None, None, None, [record], [], [], [], None, None),
                               {'set_id': 'extra', 'equip_params': [{}]}, 0, 1)

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
