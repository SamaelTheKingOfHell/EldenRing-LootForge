"""
Automated unit tests for LootForge Qt GUI application.

Verifies:
- Headless Qt window initialization
- Manual folder pickers and path input synchronizations
- Mod Engine vs. Vanilla regulation presets
- Drop rate table and enum controls
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

# Headless Qt environment
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.qt_app import (
    QApplication, LootForgeMainWindow, AdditionType, AntiDup
)
from src.config import LootForgeConfig


class TestLootForgeQtApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(["test", "-platform", "offscreen"])

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir)
        (self.base_path / "data").mkdir(parents=True)
        (self.base_path / "input_mods").mkdir(parents=True)
        (self.base_path / "mod").mkdir(parents=True)
        (self.base_path / "backups").mkdir(parents=True)

        # Minimal knowledge base files
        with open(self.base_path / "data" / "vanilla_armors.json", "w", encoding="utf-8") as f:
            f.write("[]")
        with open(self.base_path / "data" / "vanilla_weapons.json", "w", encoding="utf-8") as f:
            f.write("[]")
        with open(self.base_path / "data" / "boss_remembrances.json", "w", encoding="utf-8") as f:
            f.write("[]")
        with open(self.base_path / "data" / "enemy_drop_tables.json", "w", encoding="utf-8") as f:
            f.write("[]")

        # Initial config
        cfg = LootForgeConfig(
            game_directory=str(self.base_path / "Game"),
            input_directory="input_mods",
            output_directory="mod",
            backup_directory="backups",
            manifest_file="lootforge_manifest.json"
        )
        cfg.save(str(self.base_path / "config.json"))

        self.window = LootForgeMainWindow(self.base_path)

    def tearDown(self):
        self.window.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_window_initialization_and_folder_inputs(self):
        """Verify that folder text fields populate from config on launch."""
        self.assertEqual(self.window.input_dir_input.text(), "input_mods")
        self.assertEqual(self.window.output_dir_input.text(), "mod")
        self.assertEqual(self.window.game_dir_input.text(), str(self.base_path / "Game"))

    def _prepare_paired_capacity(self):
        """Controlled capacity results exercise real checkbox/config/Qt signal wiring."""
        from src.variant_capacity import VariantCapacity
        from src.ui.param_widget_factory import QCheckBox
        from src.ui.param_schema import get_generator_param_descriptors
        controller = self.window.capacity_controller
        controller.timer.stop()
        controller.source = self.base_path / "capacity-source.bin"
        controller.source.write_bytes(b"controlled-source")
        tool = self.base_path / "capacity-tool.dll"
        tool.write_bytes(b"controlled-tool")
        self.window.regulation_manager.regtool_dll = tool
        controller.source_identity = controller.current_source_identity()
        self.window.config.diablo_variants_per_item = 39
        self.window.config.diablo_use_vanilla_base_items = False
        capacities = {False: VariantCapacity(39, {}, {}, ()), True: VariantCapacity(30, {}, {}, ())}
        controller.apply((controller.revision, capacities))
        label = next(d.label for d in get_generator_param_descriptors() if d.key == "diablo_use_vanilla_base_items")
        toggle = next(w for w in self.window.findChildren(QCheckBox)
                      if " ".join(w.text().split()) == label)
        return controller, toggle, capacities

    def test_vanilla_toggle_immediately_clamps_and_persists_without_event_loop(self):
        controller, toggle, _ = self._prepare_paired_capacity()
        for mode, maximum, value in [(True, 30, 30), (False, 39, 30), (True, 30, 30)]:
            toggle.setChecked(mode)
            self.assertEqual(self.window.diablo_variants_spin.maximum(), maximum)
            self.assertEqual(self.window.diablo_variants_spin.value(), value)
            self.assertEqual(LootForgeConfig.load(self.window.config_path).diablo_variants_per_item, value)
            self.assertFalse(controller.timer.isActive())
        self.window.diablo_variants_spin.setValue(5)
        toggle.setChecked(False)
        self.assertEqual(self.window.diablo_variants_spin.value(), 5)

    def test_changed_source_invalidates_paired_limits(self):
        controller, toggle, _ = self._prepare_paired_capacity()
        controller.source.write_bytes(b"changed controlled source")
        toggle.setChecked(True)
        self.assertIsNone(controller.capacities)
        self.assertFalse(self.window.diablo_variants_spin.isEnabled())
        self.assertFalse(self.window.forge_btn.isEnabled())
        self.assertTrue(controller.timer.isActive())

    def test_stale_worker_result_and_failure_do_not_restore_old_limit(self):
        controller, toggle, capacities = self._prepare_paired_capacity()
        old_revision = controller.revision
        toggle.setChecked(True)
        controller.apply((old_revision, capacities))
        controller.worker_failed((old_revision, "old source failure"))
        self.assertEqual(self.window.diablo_variants_spin.maximum(), 30)
        self.assertEqual(self.window.diablo_variants_spin.value(), 30)
        self.assertNotIn("old source failure", self.window.diablo_variants_spin.toolTip())

    def test_input_dir_changed_updates_config(self):
        """Verify that modifying the input folder input field updates configuration."""
        custom_input = str(self.base_path / "custom_input")
        self.window.input_dir_input.setText(custom_input)
        self.assertEqual(self.window.config.input_directory, custom_input)

        # Verify persisted to disk
        reloaded = LootForgeConfig.load(str(self.base_path / "config.json"))
        self.assertEqual(reloaded.input_directory, custom_input)

    def test_output_dir_changed_updates_config_and_renumberer(self):
        """Verify that changing output folder updates renumberer staging target."""
        custom_output = str(self.base_path / "custom_output")
        self.window.output_dir_input.setText(custom_output)
        self.assertEqual(self.window.config.output_directory, custom_output)
        self.assertEqual(str(self.window.asset_renumberer.output_dir), custom_output)

        reloaded = LootForgeConfig.load(str(self.base_path / "config.json"))
        self.assertEqual(reloaded.output_directory, custom_output)

    def test_game_dir_changed_updates_config(self):
        """Verify that modifying the game folder input field updates configuration."""
        custom_game = str(self.base_path / "steam_custom" / "Game")
        self.window.game_dir_input.setText(custom_game)
        self.assertEqual(self.window.config.game_directory, custom_game)

        reloaded = LootForgeConfig.load(str(self.base_path / "config.json"))
        self.assertEqual(reloaded.game_directory, custom_game)

    def test_mod_engine_and_vanilla_preset_buttons(self):
        """Verify quick preset buttons for Mod Engine and Vanilla regulation."""
        self.window._set_mod_engine_reg()
        expected_mod_reg = str(self.base_path / "mod" / "regulation.bin")
        self.assertEqual(self.window.active_reg_input.text(), expected_mod_reg)
        self.assertEqual(self.window.config.active_regulation_path, expected_mod_reg)

        self.window._set_vanilla_reg()
        expected_vanilla = os.path.join(str(self.base_path / "Game"), "regulation.bin")
        self.assertEqual(self.window.active_reg_input.text(), expected_vanilla)
        self.assertEqual(self.window.config.active_regulation_path, expected_vanilla)

    def test_global_multiplier_and_spoil_toggles(self):
        """Verify drop rate multiplier slider and mystery mode toggle."""
        self.window._on_multiplier_changed(150)
        self.assertEqual(self.window.global_multiplier_percent, 150.0)

        initial_spoil = self.window.global_spoiled
        self.window._toggle_global_spoil()
        self.assertNotEqual(self.window.global_spoiled, initial_spoil)
        self.window._toggle_global_spoil()
        self.assertEqual(self.window.global_spoiled, initial_spoil)

    def test_ui_splitter_and_scroll_responsiveness(self):
        """Verify that QSplitter and QScrollArea provide adjustable, responsive layout."""
        self.assertIsNotNone(self.window.main_splitter)
        self.assertEqual(self.window.main_splitter.count(), 2)
        self.assertFalse(self.window.main_splitter.childrenCollapsible())
        self.assertTrue(self.window.top_scroll.widgetResizable())

    def test_banner_collapse_and_expand(self):
        """Verify that the Mod Manager banner can be collapsed to save vertical space."""
        # Initial state: not hidden
        self.assertFalse(self.window.banner_desc.isHidden())
        self.assertIn("Collapse", self.window.banner_toggle_btn.text())

        # Collapse
        self.window._toggle_banner()
        self.assertTrue(self.window.banner_desc.isHidden())
        self.assertIn("Expand", self.window.banner_toggle_btn.text())

        # Expand back
        self.window._toggle_banner()
        self.assertFalse(self.window.banner_desc.isHidden())
        self.assertIn("Collapse", self.window.banner_toggle_btn.text())

    def test_page_size_selector_scaling(self):
        """Verify dynamic items per page selector for large display scaling."""
        # Setup dummy drop configs to test pagination
        from src.models import ItemDropConfig
        self.window.drop_configs = [
            ItemDropConfig(item_key=f"item_{i}", name=f"Item {i}", vanilla_rate=10.0, user_rate=10.0, source_entity="Mob")
            for i in range(30)
        ]
        self.window._render_table_page()
        self.assertEqual(self.window.items_table.rowCount(), 8)

        # Switch to 15 per page
        idx_15 = self.window.page_size_combo.findData(15)
        self.window.page_size_combo.setCurrentIndex(idx_15)
        self.assertEqual(self.window.items_per_page, 15)
        self.assertEqual(self.window.items_table.rowCount(), 15)
        self.assertIn("Page 1 of 2", self.window.page_label.text())

        # Switch to All items (-1)
        idx_all = self.window.page_size_combo.findData(-1)
        self.window.page_size_combo.setCurrentIndex(idx_all)
        self.assertEqual(self.window.items_per_page, 30)
        self.assertEqual(self.window.items_table.rowCount(), 30)
        self.assertIn("Page 1 of 1", self.window.page_label.text())

    def test_minimum_window_dimensions(self):
        """Verify window sets accessible minimum dimensions for unmaximized state."""
        self.assertGreaterEqual(self.window.minimumWidth(), 800)
        self.assertGreaterEqual(self.window.minimumHeight(), 500)

    def test_config_persistence_round_trip(self):
        """Verify all user preference fields survive a save→load cycle."""
        cfg = self.window.config
        cfg_path = str(self.base_path / "config.json")

        # Set non-default values for every user preference
        cfg.addition_type = 3           # Test Mode enum
        cfg.anti_dup = 2                # Everything-in-the-Wild enum
        cfg.global_multiplier_percent = 75.5
        cfg.global_spoiled = False
        cfg.items_per_page = 15
        cfg.banner_collapsed = True
        cfg.user_drop_rates = {"item_abc": 42.0, "item_xyz": 5.5}
        cfg.item_spoiled_states = {"item_abc": False, "item_xyz": True}
        cfg.save(cfg_path)

        # Reload from disk and verify every field
        loaded = LootForgeConfig.load(cfg_path)
        self.assertEqual(loaded.addition_type, 3)
        self.assertEqual(loaded.anti_dup, 2)
        self.assertAlmostEqual(loaded.global_multiplier_percent, 75.5)
        self.assertFalse(loaded.global_spoiled)
        self.assertEqual(loaded.items_per_page, 15)
        self.assertTrue(loaded.banner_collapsed)
        self.assertEqual(loaded.user_drop_rates, {"item_abc": 42.0, "item_xyz": 5.5})
        self.assertEqual(loaded.item_spoiled_states, {"item_abc": False, "item_xyz": True})

        # Also verify core paths survived
        self.assertEqual(loaded.input_directory, "input_mods")
        self.assertEqual(loaded.output_directory, "mod")


if __name__ == "__main__":
    unittest.main()

