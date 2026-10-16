"""Reported game regressions: useful effects, independent auras and untouched vanilla text."""
import json
import tempfile
import unittest
from pathlib import Path
from src.config import LootForgeConfig
from src.diablo_affixes import AFFIX_POOL, RarityTier
from src.diablo_generator import DiabloLootGenerator
from src.knowledge_base import VanillaKnowledgeBase


class RefinementChecks(unittest.TestCase):
    def test_disabling_region_scaling_does_not_turn_additive_stats_into_replacements(self):
        gen = DiabloLootGenerator(progression_scaling=False)
        fiery = next(a for a in AFFIX_POOL if a.name == "Fiery")
        fields = {}
        gen.apply_affixes_to_equipment(fields, [fiery], is_weapon=True)
        self.assertEqual(fields["_lf_diablo_stat_deltas"]["attackBaseFire"], fiery.field_modifiers["attackBaseFire"])
        self.assertNotIn("_lf_diablo_power", fields)

    def test_starting_resource_bonus_survives_character_stat_rounding(self):
        from src.diablo_power import extra_passives
        import random
        seen = set()
        for _ in range(100):
            for affix in extra_passives(random.Random(_), RarityTier.MYTHIC, 0.1):
                for field, value in affix.native_fields.items():
                    if field in ("maxHpRate", "maxMpRate", "maxStaminaRate"):
                        seen.add(field)
                        self.assertGreaterEqual(int(70 * value) - 70, 1)
        self.assertEqual(seen, {"maxHpRate", "maxMpRate", "maxStaminaRate"})

    def test_actual_qt_aura_controls_are_separate_booleans(self):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from src.qt_app import QApplication
        from src.ui.param_schema import get_generator_param_descriptors
        from src.ui.param_widget_factory import ParamWidgetFactory
        app = QApplication.instance() or QApplication([])
        config = LootForgeConfig(diablo_loot_enabled=True)
        changes = []
        card, controls = ParamWidgetFactory.build_diablo_card(get_generator_param_descriptors(), config,
            lambda key, value: changes.append((key, value)))
        weapon = controls["diablo_weapon_auras_enabled"]
        armor = controls["diablo_armor_auras_enabled"]
        self.assertNotIn("diablo_auras_enabled", controls)
        weapon.setChecked(True)
        app.processEvents()
        self.assertTrue(weapon.isChecked())
        self.assertFalse(armor.isChecked())
        armor.setChecked(True)
        weapon.setChecked(False)
        app.processEvents()
        self.assertFalse(weapon.isChecked())
        self.assertTrue(armor.isChecked())
        self.assertIn(("diablo_weapon_auras_enabled", False), changes)
        self.assertIn(("diablo_armor_auras_enabled", True), changes)
        card.deleteLater()

    def test_aura_categories_are_independent_and_do_not_change_combat_fields(self):
        affix = next(a for a in AFFIX_POOL if a.name == "Fiery")
        for weapon_aura, armor_aura in ((True, False), (False, True), (False, False), (True, True)):
            gen = DiabloLootGenerator(weapon_auras_enabled=weapon_aura, armor_auras_enabled=armor_aura)
            for weapon in (True, False):
                fields = {}
                gen.apply_affixes_to_equipment(fields, [affix], is_weapon=weapon)
                self.assertEqual("_lf_diablo_aura" in fields, weapon_aura if weapon else armor_aura)
                self.assertGreater(fields["attackBaseFire"], 0)

    def test_legacy_aura_setting_migrates_without_overriding_explicit_category(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"diablo_auras_enabled": True, "diablo_armor_auras_enabled": False}))
            config = LootForgeConfig.load(str(path))
            self.assertTrue(config.diablo_weapon_auras_enabled)
            self.assertFalse(config.diablo_armor_auras_enabled)
            config.save(str(path))
            data = json.loads(path.read_text())
            self.assertNotIn("diablo_auras_enabled", data)
            self.assertTrue(data["diablo_weapon_auras_enabled"])
            self.assertFalse(data["diablo_armor_auras_enabled"])

    def test_positive_rolls_do_not_round_into_zero_or_overwrite_native_buildup(self):
        gen = DiabloLootGenerator(seed=4, extra_passives=True)
        for _ in range(500):
            affixes = gen.roll_affixes(RarityTier.LEGENDARY, True, tier=1)
            fields = {}
            gen.apply_affixes_to_equipment(fields, affixes, is_weapon=True)
            for affix in affixes:
                self.assertTrue(all(value > 0 for value in affix.field_modifiers.values()))
            self.assertTrue(all(power >= 0.5 for power in fields.get("_lf_diablo_passive_scales", {}).values()))
            self.assertNotIn("spEffectBehaviorId0", fields)
            self.assertNotRegex(gen.build_caption_with_affixes("", RarityTier.LEGENDARY, affixes), r"\bx0(?:\s|$)")

    def test_all_vanilla_infusions_preserve_text_and_prices(self):
        specs = DiabloLootGenerator(seed=9, extra_passives=True).generate_vanilla_stat_injections(
            VanillaKnowledgeBase.from_data_dir("data"))
        self.assertGreater(len(specs), 500)
        for spec in specs:
            self.assertFalse(spec["fmg_texts"])
            for ep in spec["equip_params"]:
                self.assertTrue(ep["update_existing"])
                for name in ("sellValue", "saleValue", "basicPrice"):
                    self.assertNotIn(name, ep["field_updates"])
