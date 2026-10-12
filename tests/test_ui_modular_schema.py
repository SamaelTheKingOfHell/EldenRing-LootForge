"""
Automated unit tests for LootForge UI modular parameter schema, widget factory,
and the interactive Loot Review Modal dialog per [CS-MODULAR] and [CS-DECOUPLE].
"""

import os
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.config import LootForgeConfig
from src.models import AdditionType, AntiDup, ItemDropConfig
from src.ui.param_schema import (
    ParamType, ParamPurpose, ParamDescriptor, get_generator_param_descriptors
)
from src.ui.param_widget_factory import ParamWidgetFactory
from src.ui.loot_modal import LootReviewModal


class TestUIModularSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(["test", "-platform", "offscreen"])

    def test_param_descriptors_completeness_and_purposes(self):
        """Verify generator parameter descriptors cover all required purposes and types."""
        descriptors = get_generator_param_descriptors()
        keys = {d.key: d for d in descriptors}

        # Drop Style (Enums & scaling)
        self.assertIn("addition_type", keys)
        self.assertEqual(keys["addition_type"].param_type, ParamType.ENUM)
        self.assertEqual(keys["addition_type"].purpose, ParamPurpose.DROP_STYLE)
        self.assertIsNotNone(keys["addition_type"].enum_options)

        self.assertIn("anti_dup", keys)
        self.assertEqual(keys["anti_dup"].param_type, ParamType.ENUM)
        self.assertEqual(keys["anti_dup"].purpose, ParamPurpose.DROP_STYLE)

        self.assertIn("global_multiplier_percent", keys)
        self.assertEqual(keys["global_multiplier_percent"].param_type, ParamType.FLOAT)

        # Diablo Procedural ARPG Generator
        self.assertIn("diablo_loot_enabled", keys)
        self.assertEqual(keys["diablo_loot_enabled"].param_type, ParamType.BOOL)
        self.assertEqual(keys["diablo_loot_enabled"].purpose, ParamPurpose.DIABLO_ARPG)

        self.assertIn("diablo_variants_per_item", keys)
        self.assertEqual(keys["diablo_variants_per_item"].param_type, ParamType.INT)
        self.assertEqual(keys["diablo_variants_per_item"].purpose, ParamPurpose.DIABLO_ARPG)
        self.assertEqual(keys["diablo_variants_per_item"].max_value, 1000)

        self.assertIn("diablo_seed", keys)
        self.assertEqual(keys["diablo_seed"].param_type, ParamType.INT)

        self.assertIn("diablo_randomize_weapon_skills", keys)
        self.assertEqual(keys["diablo_randomize_weapon_skills"].param_type, ParamType.BOOL)
        self.assertEqual(keys["diablo_randomize_weapon_skills"].purpose, ParamPurpose.DIABLO_ARPG)

        # Paths
        self.assertIn("active_regulation_path", keys)
        self.assertEqual(keys["active_regulation_path"].param_type, ParamType.PATH_FILE)
        self.assertEqual(keys["active_regulation_path"].purpose, ParamPurpose.PATHS)

        self.assertIn("input_directory", keys)
        self.assertEqual(keys["input_directory"].param_type, ParamType.PATH_DIR)

    def test_param_widget_factory_card_generation(self):
        """Verify ParamWidgetFactory produces functional cards with correct control widgets."""
        descriptors = get_generator_param_descriptors()
        cfg = LootForgeConfig()
        changes = {}

        def _on_change(k, v):
            changes[k] = v

        # Test Drop Style Card
        drop_card, drop_ctrls = ParamWidgetFactory.build_drop_style_card(
            descriptors, cfg, _on_change
        )
        self.assertIsNotNone(drop_card)
        self.assertIn("addition_type", drop_ctrls)
        self.assertIn("anti_dup", drop_ctrls)
        self.assertIn("global_multiplier_percent", drop_ctrls)

        # Test Diablo Card
        diablo_card, diablo_ctrls = ParamWidgetFactory.build_diablo_card(
            descriptors, cfg, _on_change
        )
        self.assertIsNotNone(diablo_card)
        self.assertIn("diablo_loot_enabled", diablo_ctrls)
        self.assertIn("diablo_variants_per_item", diablo_ctrls)
        self.assertIn("diablo_seed", diablo_ctrls)
        self.assertIn("diablo_randomize_weapon_skills", diablo_ctrls)

        # Toggle diablo enabled checkbox
        cb = diablo_ctrls["diablo_loot_enabled"]
        cb.setChecked(True)
        self.assertTrue(changes.get("diablo_loot_enabled"))

        # Modify variants spinbox
        spin = diablo_ctrls["diablo_variants_per_item"]
        spin.setValue(10)
        self.assertEqual(changes.get("diablo_variants_per_item"), 10)

    def test_loot_review_modal_filtering_and_rate_updates(self):
        """Verify LootReviewModal search filtering, rate synchronization, and spoil toggles."""
        rate_changes = []

        modal = LootReviewModal(
            on_rate_changed=lambda cfg, val: rate_changes.append((cfg.item_key, val)),
            distributor=None
        )

        test_items = [
            ItemDropConfig("item_1", "Malenia Armor Set", 5.0, 5.0, is_spoiled=False, source_entity="Malenia Boss"),
            ItemDropConfig("item_2", "Radahn Greatsword", 10.0, 10.0, is_spoiled=False, source_entity="Radahn Boss"),
            ItemDropConfig("item_3", "Knight Helm", 20.0, 20.0, is_spoiled=False, source_entity="Godrick Soldier"),
        ]

        modal.set_data(test_items, global_multiplier=100.0, global_spoiled=False, items_per_page=8, diablo_enabled=True)
        self.assertEqual(modal.items_table.rowCount(), 3)
        self.assertIn("Diablo ARPG: Active", modal.stats_badge.text())

        # Test search filter
        modal.search_input.setText("Radahn")
        self.assertEqual(modal.items_table.rowCount(), 1)
        self.assertEqual(modal.items_table.item(0, 0).text(), "Radahn Greatsword")

        # Clear search filter
        modal.search_input.setText("")
        self.assertEqual(modal.items_table.rowCount(), 3)

        # Test user rate change callback
        spinbox = modal.items_table.cellWidget(0, 3)
        self.assertIsNotNone(spinbox)
        spinbox.setValue(45.0)
        self.assertIn(("item_1", 45.0), rate_changes)


if __name__ == "__main__":
    unittest.main()
