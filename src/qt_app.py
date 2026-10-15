"""
PyQt6 / PySide6 Desktop GUI for LootForge.

Features:
- Dark Souls fantasy theme with gold accents and responsive layout
- Prominent Mod Manager warning banner
- Schema-driven automatic parameter generation by type and purpose [CS-DECOUPLE]
- Dedicated interactive Loot Review Modal dialog for drop tables
- Diablo-style procedural ARPG loot engine with affixes, rarities, and SpEffects
- Floating real-time Developer Console drawer [CS-DEBUG]
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QDoubleSpinBox
    from PySide6.QtCore import QTimer
except (ImportError, Exception):
    from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QDoubleSpinBox
    from PyQt6.QtCore import QTimer

from src.config import LootForgeConfig
from src.knowledge_base import VanillaKnowledgeBase
from src.id_allocator import IdAllocator
from src.scanner import ModScanner
from src.asset_renumberer import AssetRenumberer
from src.param_builder import ParamBuilder
from src.backup_manager import BackupManager
from src.manifest_store import ManifestStore
from src.loot_distributor import LootDistributor
from src.regulation_manager import RegulationManager
from src.models import AdditionType, AntiDup, DetectedModSet, ItemDropConfig
from src.logger import system_logger
from src.ui.theme import DARK_SOULS_QSS
from src.ui.loot_modal import LootReviewModal
from src.ui.main_window_builder import MainWindowBuilder
from src.ui.patch_orchestrator import PatchOrchestrator
from src.ui.mod_scanner_service import ModScannerService


class LootForgeMainWindow(QMainWindow):
    """
    Main Qt Window for LootForge.
    Coordinates settings cards, the interactive Loot Modal, and mod injection.
    """

    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir
        self.config_path = str(base_dir / "config.json")
        self.config = LootForgeConfig.load(self.config_path)
        self.knowledge_base = VanillaKnowledgeBase.from_data_dir(str(base_dir / "data"))
        self.id_allocator = IdAllocator(
            min_model_id=self.config.min_model_id,
            max_model_id=self.config.max_model_id,
            base_param_id=self.config.base_param_id,
            base_item_lot_id=self.config.base_item_lot_id
        )
        self.scanner = ModScanner(self.knowledge_base)
        out_p = Path(self.config.output_directory)
        self.asset_renumberer = AssetRenumberer(str(self.base_dir / out_p if not out_p.is_absolute() else out_p))
        self.param_builder = ParamBuilder(self.knowledge_base)
        backup_p = Path(self.config.backup_directory)
        self.backup_manager = BackupManager(str(self.base_dir / backup_p if not backup_p.is_absolute() else backup_p))
        manifest_p = Path(self.config.manifest_file)
        self.manifest_store = ManifestStore(str(self.base_dir / manifest_p if not manifest_p.is_absolute() else manifest_p))
        self.distributor = LootDistributor(self.knowledge_base)
        self.regulation_manager = RegulationManager(base_dir)

        # Operational state
        self.scanned_sets: List[DetectedModSet] = []
        self.drop_configs: List[ItemDropConfig] = []
        self.global_multiplier_percent: float = getattr(self.config, "global_multiplier_percent", 100.0)
        self.global_spoiled: bool = getattr(self.config, "global_spoiled", True)
        self.banner_collapsed: bool = getattr(self.config, "banner_collapsed", False)
        self.items_per_page: int = getattr(self.config, "items_per_page", 8)

        self.setWindowTitle("LootForge: Elden Ring Relic & Loot Injector (Qt Edition)")
        self.resize(1150, 850)
        self.setMinimumSize(850, 520)
        self.setStyleSheet(DARK_SOULS_QSS)

        self._init_modal()
        MainWindowBuilder.build_main_ui(self)
        from src.ui.variant_capacity_controller import VariantCapacityController
        self.capacity_controller = VariantCapacityController(self)
        self._load_initial_data()

        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._poll_logs)
        self.log_timer.start(1500)

    def _init_modal(self):
        self.loot_modal = LootReviewModal(
            parent=self,
            on_rate_changed=self._on_user_rate_changed,
            on_rate_reset=self._reset_item_rate,
            on_spoil_toggle=self._toggle_item_spoil,
            on_global_spoil_toggle=self._toggle_global_spoil,
            on_page_size_changed=self._on_page_size_changed_from_modal,
            on_custom_art_toggle=self._on_custom_art_toggled,
            distributor=self.distributor
        )

    # Test compatibility properties delegating to the modal
    @property
    def items_table(self): return self.loot_modal.items_table
    @property
    def page_size_combo(self): return self.loot_modal.page_size_combo
    @property
    def page_label(self): return self.loot_modal.page_label
    @property
    def prev_page_btn(self): return self.loot_modal.prev_page_btn
    @property
    def next_page_btn(self): return self.loot_modal.next_page_btn
    @property
    def global_spoil_btn(self): return self.loot_modal.global_spoil_btn
    @property
    def items_per_page(self):
        return self.loot_modal.items_per_page if hasattr(self, "loot_modal") else getattr(self, "_items_per_page", 8)

    @items_per_page.setter
    def items_per_page(self, val: int):
        self._items_per_page = val
        if hasattr(self, "loot_modal"): self.loot_modal.items_per_page = val

    def _open_loot_modal(self):
        self._ensure_all_deep_introspected()
        self._sync_modal_data()
        self.loot_modal.exec()

    def _sync_modal_data(self):
        self.loot_modal.set_data(
            drop_configs=self.drop_configs,
            global_multiplier=self.global_multiplier_percent,
            global_spoiled=self.global_spoiled,
            items_per_page=self.items_per_page,
            diablo_enabled=self.config.diablo_loot_enabled,
            skills_movesets_enabled=getattr(self.config, "import_custom_skills_movesets", True)
        )

    def _render_table_page(self):
        self._sync_modal_data()
        self.loot_modal.render_table_page()

    def _on_param_changed(self, key: str, value: Any):
        setattr(self.config, key, value)
        self.config.save(self.config_path)
        if key in ("addition_type", "anti_dup"):
            self._recalculate_distribution()
        elif key == "global_multiplier_percent":
            self.global_multiplier_percent = float(value)
            self._sync_modal_data()
        elif key == "output_directory":
            out_p = Path(value)
            if not out_p.is_absolute():
                out_p = self.base_dir / out_p
            self.asset_renumberer.output_dir = out_p
        elif key in ("diablo_loot_enabled", "import_custom_skills_movesets"):
            self._sync_modal_data()
        if key in ("active_regulation_path", "game_directory", "output_directory", "diablo_use_vanilla_base_items", "diablo_inject_vanilla_stats", "diablo_loot_enabled") and hasattr(self, "capacity_controller"):
            self.capacity_controller.schedule(vanilla_only=key == "diablo_use_vanilla_base_items")

    def _on_page_size_changed_from_modal(self, val: int):
        self.items_per_page = val
        self.config.items_per_page = val
        self.config.save(self.config_path)

    def _on_multiplier_changed(self, val: int):
        self._on_param_changed("global_multiplier_percent", float(val))
        if hasattr(self, "mult_slider"):
            self.mult_slider.blockSignals(True)
            self.mult_slider.setValue(val)
            self.mult_slider.blockSignals(False)

    def _toggle_banner(self):
        self.banner_collapsed = not self.banner_collapsed
        self.banner_desc.setVisible(not self.banner_collapsed)
        self.banner_toggle_btn.setText("▼ Expand Notice" if self.banner_collapsed else "▲ Collapse Notice")
        self.config.banner_collapsed = self.banner_collapsed
        self.config.save(self.config_path)

    def _toggle_global_spoil(self):
        self.global_spoiled = not self.global_spoiled
        self.config.global_spoiled = self.global_spoiled
        self.config.save(self.config_path)
        self._sync_modal_data()

    def _toggle_dev_console(self):
        self.console_drawer.setVisible(not self.console_drawer.isVisible())

    def _load_initial_data(self):
        if not self.config.active_regulation_path:
            self.config.active_regulation_path = self.config.resolve_active_regulation_bin()
            if hasattr(self, "active_reg_input"):
                self.active_reg_input.setText(self.config.active_regulation_path)
        self._scan_mods()

    def _set_mod_engine_reg(self):
        out_p = Path(self.config.output_directory)
        mod_reg = str((self.base_dir / out_p if not out_p.is_absolute() else out_p) / "regulation.bin")
        self.active_reg_input.setText(mod_reg)
        self.config.active_regulation_path = mod_reg
        self.config.save(self.config_path)
        system_logger.info(f"Targeting Mod Engine regulation: {mod_reg}", source="GUI")

    def _set_vanilla_reg(self):
        if self.config.game_directory:
            vanilla_reg = os.path.join(self.config.game_directory, "regulation.bin")
            self.active_reg_input.setText(vanilla_reg)
            self.config.active_regulation_path = vanilla_reg
            self.config.save(self.config_path)
            system_logger.info(f"Targeting Vanilla regulation: {vanilla_reg}", source="GUI")

    @staticmethod
    def _format_mod_display_name(folder_name: str) -> str:
        return ModScannerService.format_mod_display_name(folder_name)

    def _ensure_all_deep_introspected(self):
        ModScannerService.ensure_all_deep_introspected(
            base_dir=self.base_dir,
            config=self.config,
            scanned_sets=self.scanned_sets,
            drop_configs=self.drop_configs
        )

    def _scan_mods(self):
        try:
            self.scanned_sets, self.drop_configs = ModScannerService.scan_mods(
                base_dir=self.base_dir,
                config=self.config,
                scanner=self.scanner,
                id_allocator=self.id_allocator
            )
            self.summary_badge.setText(f"{len(self.scanned_sets)} Mod Sets Detected ({len(self.drop_configs)} Items)")
            self.open_modal_btn.setText(f"👁 Open Loot Distribution Modal ({len(self.drop_configs)} Items)")
            self._recalculate_distribution()
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Error scanning mods: {e}")

    def _recalculate_distribution(self):
        add_type = AdditionType(self.addition_type_combo.currentData()) if hasattr(self, "addition_type_combo") else AdditionType(self.config.addition_type)
        anti_dup = AntiDup(self.anti_dup_combo.currentData()) if hasattr(self, "anti_dup_combo") else AntiDup(self.config.anti_dup)
        ModScannerService.recalculate_distribution(
            config=self.config,
            config_path=self.config_path,
            distributor=self.distributor,
            scanned_sets=self.scanned_sets,
            drop_configs=self.drop_configs,
            addition_type=add_type,
            anti_dup=anti_dup,
            global_multiplier_percent=self.global_multiplier_percent
        )
        self._sync_modal_data()
        if hasattr(self, "capacity_controller"):
            self.capacity_controller.schedule()

    def _on_user_rate_changed(self, cfg: ItemDropConfig, val: float):
        ModScannerService.update_item_user_rate(self.config, self.config_path, cfg, val)

    def _reset_item_rate(self, cfg: ItemDropConfig, spinbox: QDoubleSpinBox):
        ModScannerService.reset_item_rate(self.config, self.config_path, cfg, spinbox)

    def _toggle_item_spoil(self, cfg: ItemDropConfig):
        ModScannerService.toggle_item_spoil(self.config, self.config_path, cfg)

    def _on_custom_art_toggled(self, cfg: ItemDropConfig, is_enabled: bool):
        ModScannerService.toggle_custom_art(self.config, self.config_path, self.scanned_sets, cfg, is_enabled)

    def _create_backup(self):
        PatchOrchestrator.create_backup(self)

    def _restore_backup(self):
        PatchOrchestrator.restore_backup(self)

    def _forge_mods(self):
        PatchOrchestrator.forge_mods_dialog(self)

    def _uninstall_mods(self):
        PatchOrchestrator.uninstall_mods(self)

    def _poll_logs(self):
        logs = system_logger.get_recent_logs(limit=50)
        self.console_text.clear()
        for l in logs:
            self.console_text.append(f"[{l['timestamp'].split(' ')[1]}] [{l['level']}] [{l['source']}] {l['message']}")


def main():
    app = QApplication(sys.argv)
    base_dir = Path(__file__).resolve().parent.parent
    window = LootForgeMainWindow(base_dir=base_dir)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
