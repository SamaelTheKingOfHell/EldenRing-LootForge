"""Deterministic balance and toggle regressions, independent of game runtime."""
import json
import tempfile
import unittest
from pathlib import Path

from src.config import LootForgeConfig
from src.diablo_affixes import RarityTier, AFFIX_POOL
from src.diablo_generator import DiabloLootGenerator
from src.diablo_power import extra_passives
from src.models import ProgressionTier


class DiabloPowerChecks(unittest.TestCase):
    def test_affix_minimum_rarity_is_enforced(self):
        ranks = list(RarityTier)
        gen = DiabloLootGenerator(seed=21)
        for rarity in ranks:
            for _ in range(200):
                for aff in gen.roll_affixes(rarity, True):
                    self.assertLessEqual(ranks.index(aff.tier_min), ranks.index(rarity))

    def test_late_legendary_rolls_are_stronger(self):
        early = DiabloLootGenerator(seed=19)
        late = DiabloLootGenerator(seed=19)
        a = early.roll_affixes(RarityTier.LEGENDARY, True, tier=ProgressionTier.EARLY)
        b = late.roll_affixes(RarityTier.LEGENDARY, True, tier=ProgressionTier.ENDGAME)
        self.assertEqual([x.name for x in a], [x.name for x in b])
        for x, y in zip(a, b):
            self.assertGreater(y.power_scale, x.power_scale * 3)
            for key in x.field_modifiers:
                self.assertGreaterEqual(y.field_modifiers[key], x.field_modifiers[key])

    def test_early_legendary_is_possible_and_rare(self):
        gen = DiabloLootGenerator(seed=42)
        rolls = [gen.roll_rarity(tier=ProgressionTier.EARLY) for _ in range(10000)]
        count = rolls.count(RarityTier.LEGENDARY)
        self.assertGreater(count, 100)
        self.assertLess(count, 300)

    def test_boss_and_chest_rarity_also_follows_progression(self):
        for flags in ({"is_boss": True}, {"is_chest": True}):
            early, late = DiabloLootGenerator(seed=6), DiabloLootGenerator(seed=6)
            a = [early.roll_rarity(tier=1, **flags) for _ in range(10000)]
            b = [late.roll_rarity(tier=4, **flags) for _ in range(10000)]
            high = lambda values: sum(x in (RarityTier.LEGENDARY, RarityTier.MYTHIC) for x in values)
            self.assertGreater(high(a), 100)
            self.assertLess(high(a), 2000)
            self.assertGreater(high(b), high(a) * 3)

    def test_proc_rarity_category_and_frequency(self):
        for weapon, shield, allowed in (
            (True, False, {"attack_cast"}), (True, True, {"guard_cast", "guard_heal"}),
            (False, False, {"thorns", "hurt_heal"})):
            gen = DiabloLootGenerator(seed=3, triggered_effects=True)
            for rarity in (RarityTier.COMMON, RarityTier.MAGIC, RarityTier.RARE):
                for _ in range(100):
                    self.assertFalse(any(a.proc_kind for a in gen.roll_affixes(rarity, weapon, is_shield=shield)))
            for rarity, low, high in ((RarityTier.LEGENDARY, 25, 100), (RarityTier.MYTHIC, 80, 210)):
                procs = [a.proc_kind for _ in range(1000)
                         for a in gen.roll_affixes(rarity, weapon, is_shield=shield) if a.proc_kind]
                self.assertTrue(set(procs) <= allowed)
                self.assertGreater(len(procs), low)
                self.assertLess(len(procs), high)

    def test_disabling_optional_features_omits_native_payload(self):
        gen = DiabloLootGenerator(seed=11, progression_scaling=False)
        for _ in range(100):
            affixes = gen.roll_affixes(RarityTier.MYTHIC, True)
            fields = {}
            gen.apply_affixes_to_equipment(fields, affixes, is_weapon=True)
            self.assertFalse(any(key in fields for key in ("_lf_diablo_proc", "_lf_diablo_passives", "_lf_diablo_aura", "_lf_diablo_power")))

    def test_more_passives_are_real_native_fields(self):
        gen = DiabloLootGenerator(seed=15, extra_passives=True)
        for rarity, count in ((RarityTier.RARE, 1), (RarityTier.LEGENDARY, 2), (RarityTier.MYTHIC, 3)):
            affixes = gen.roll_affixes(rarity, True, tier=ProgressionTier.LATE)
            self.assertEqual(sum(bool(a.native_fields) for a in affixes), count)
            fields = {}
            gen.apply_affixes_to_equipment(fields, affixes, is_weapon=True)
            self.assertEqual(len(fields['_lf_diablo_passives']), count)

    def test_settings_roundtrip_and_schema(self):
        from src.ui.param_schema import get_generator_param_descriptors, ParamPurpose
        keys = ('diablo_progression_scaling', 'diablo_extra_passives', 'diablo_triggered_effects', 'diablo_weapon_auras_enabled', 'diablo_armor_auras_enabled')
        with tempfile.TemporaryDirectory() as directory:
            config = LootForgeConfig(**dict.fromkeys(keys, True))
            path = str(Path(directory) / 'settings.json')
            config.save(path)
            restored = LootForgeConfig.load(path)
            for key in keys:
                self.assertTrue(getattr(restored, key))
            descriptors = {d.key: d for d in get_generator_param_descriptors()}
            for key in keys:
                self.assertEqual(descriptors[key].purpose, ParamPurpose.DIABLO_ARPG)

    def test_single_variant_is_rolled(self):
        spec = {'set_id': 'blade', 'tier': 1, 'equip_params': [
            {'param_table': 'EquipParamWeapon', 'new_param_id': 9000000, 'base_clone_id': 2020000}],
            'fmg_texts': [], 'loot_distribution': None}
        generated = DiabloLootGenerator(seed=5).generate_variants_for_spec(spec, 1)
        self.assertIn('_lf_diablo_power', generated[0]['equip_params'][0]['field_updates'])
        self.assertNotIn('field_updates', spec['equip_params'][0])

    def test_empty_region_never_uses_other_regions(self):
        from src.diablo_distribution_context import distribution_context
        from src.knowledge_base import VanillaKnowledgeBase
        kb = VanillaKnowledgeBase({}, {'merchants': [
            {'id': 'late_only', 'name': 'Late', 'progressionTier': 3}]})
        gen = DiabloLootGenerator(seed=5)
        pools = distribution_context(gen, kb, ProgressionTier.EARLY)
        self.assertEqual(pools[5], [])
        gen.progression_scaling = False
        gen._distribution_contexts.clear()
        self.assertTrue(distribution_context(gen, kb, ProgressionTier.EARLY)[5])

    def test_auras_follow_effects_without_changing_rolls(self):
        from src.diablo_auras import aura_theme
        for name, expected in (("Fiery", "fire"), ("Shocking", "lightning"),
                               ("Glacial", "frost"), ("Venomous", "poison"),
                               ("Rot-Infused", "rot"), ("Hallowed", "holy"),
                               ("Serrated", "blood")):
            affix = next(a for a in AFFIX_POOL if a.name == name)
            self.assertEqual(aura_theme([affix]), expected)
        self.assertEqual(aura_theme([]), "")
        enabled = DiabloLootGenerator(seed=87, auras_enabled=True, extra_passives=True, triggered_effects=True)
        disabled = DiabloLootGenerator(seed=87, extra_passives=True, triggered_effects=True)
        for _ in range(200):
            a = enabled.roll_affixes(RarityTier.MYTHIC, True)
            b = disabled.roll_affixes(RarityTier.MYTHIC, True)
            self.assertEqual(a, b)
            left, right = {}, {}
            enabled.apply_affixes_to_equipment(left, a, is_weapon=True)
            disabled.apply_affixes_to_equipment(right, b, is_weapon=True)
            if aura_theme(a):
                self.assertEqual(left.pop('_lf_diablo_aura'), aura_theme(a))
            self.assertEqual(left, right)
        fields = {}
        enabled.apply_affixes_to_equipment(fields, [AFFIX_POOL[0]], is_accessory=True)
        self.assertNotIn('_lf_diablo_aura', fields)

    def test_zero_stats_multiplier_does_not_leave_combat_magic(self):
        gen = DiabloLootGenerator(seed=3, stats_multiplier=0, extra_passives=True, triggered_effects=True)
        for _ in range(200):
            fields = {}
            gen.apply_affixes_to_equipment(fields, gen.roll_affixes(RarityTier.MYTHIC, True), is_weapon=True)
            self.assertNotIn('_lf_diablo_proc', fields)
            self.assertTrue(all(value == 0 for value in fields.get('_lf_diablo_passive_scales', {}).values()))


if __name__ == '__main__':
    unittest.main()
