"""
PyQt6 / PySide6 Desktop GUI for LootForge.

Features:
- Dark Souls fantasy theme with gold accents and responsive layout
- Prominent Mod Manager warning banner
- Schema-driven automatic parameter generation by type and purpose [CS-DECOUPLE]
- Dedicated interactive Loot Review Modal dialog for drop tables
- Diablo-style procedural ARPG loot engine with affixes, rarities, and SpEffects
- Floating real-time Developer Console drawer [CS-DEBUG]
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QScrollArea, QMessageBox,
        QDialog, QSplitter, QTextEdit, QSizePolicy, QDoubleSpinBox
    )
    from PySide6.QtCore import Qt, QTimer
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QScrollArea, QMessageBox,
        QDialog, QSplitter, QTextEdit, QSizePolicy, QDoubleSpinBox
    )
    from PyQt6.QtCore import Qt, QTimer

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
from src.ui.param_schema import get_generator_param_descriptors
from src.ui.param_widget_factory import ParamWidgetFactory
from src.ui.loot_modal import LootReviewModal


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
        if not out_p.is_absolute():
            out_p = base_dir / out_p
        self.asset_renumberer = AssetRenumberer(str(out_p))
        self.param_builder = ParamBuilder(self.knowledge_base)
        backup_p = Path(self.config.backup_directory)
        if not backup_p.is_absolute():
            backup_p = base_dir / backup_p
        self.backup_manager = BackupManager(str(backup_p))
        manifest_p = Path(self.config.manifest_file)
        if not manifest_p.is_absolute():
            manifest_p = base_dir / manifest_p
        self.manifest_store = ManifestStore(str(manifest_p))
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
        self._build_ui()
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
            distributor=self.distributor
        )

    # Test compatibility properties delegating to the modal
    @property
    def items_table(self):
        return self.loot_modal.items_table

    @property
    def page_size_combo(self):
        return self.loot_modal.page_size_combo

    @property
    def page_label(self):
        return self.loot_modal.page_label

    @property
    def prev_page_btn(self):
        return self.loot_modal.prev_page_btn

    @property
    def next_page_btn(self):
        return self.loot_modal.next_page_btn

    @property
    def global_spoil_btn(self):
        return self.loot_modal.global_spoil_btn

    @property
    def items_per_page(self):
        if hasattr(self, "loot_modal"):
            return self.loot_modal.items_per_page
        return getattr(self, "_items_per_page", 8)

    @items_per_page.setter
    def items_per_page(self, val: int):
        self._items_per_page = val
        if hasattr(self, "loot_modal"):
            self.loot_modal.items_per_page = val

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title_label = QLabel("LOOTFORGE: ELDEN RING RELIC INJECTOR")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffd475; letter-spacing: 1.5px;")
        header.addWidget(title_label)

        self.summary_badge = QLabel("0 Mod Sets Detected")
        self.summary_badge.setStyleSheet(
            "background-color: #161924; color: #c5a059; border: 1px solid rgba(197, 160, 89, 0.35); "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        header.addWidget(self.summary_badge)
        header.addStretch()

        self.banner_toggle_btn = QPushButton("▲ Collapse Notice")
        self.banner_toggle_btn.clicked.connect(self._toggle_banner)
        header.addWidget(self.banner_toggle_btn)

        self.dev_console_btn = QPushButton("⚙ Dev Console")
        self.dev_console_btn.clicked.connect(self._toggle_dev_console)
        header.addWidget(self.dev_console_btn)
        main_layout.addLayout(header)

        # Splitter Layout
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)

        # Scrollable Configuration Container
        self.top_scroll = QScrollArea()
        self.top_scroll.setWidgetResizable(True)
        self.top_scroll.setFrameShape(QFrame.Shape.NoFrame)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 4, 0)
        top_layout.setSpacing(10)

        # Banner Frame
        self.banner_frame = QFrame()
        self.banner_frame.setProperty("class", "banner")
        banner_vbox = QVBoxLayout(self.banner_frame)
        banner_vbox.setContentsMargins(12, 10, 12, 10)
        banner_title = QLabel("⚠️ USING MOD ENGINE 2 OR A MOD MANAGER? READ THIS FIRST:")
        banner_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 13px;")
        banner_vbox.addWidget(banner_title)
        self.banner_desc = QLabel(
            "Always point to your CURRENT ACTIVE regulation.bin (such as mod/regulation.bin or your profile).\n"
            "LootForge injects standalone items and loot drops directly so all other mods stay 100% intact!"
        )
        self.banner_desc.setWordWrap(True)
        self.banner_desc.setStyleSheet("color: #ede8df; line-height: 1.4;")
        banner_vbox.addWidget(self.banner_desc)
        top_layout.addWidget(self.banner_frame)
        if self.banner_collapsed:
            self.banner_desc.hide()
            self.banner_toggle_btn.setText("▼ Expand Notice")

        # Schema-driven auto-generated parameter cards
        descriptors = get_generator_param_descriptors()

        # Paths Card
        paths_card, path_ctrls = ParamWidgetFactory.build_paths_card(
            descriptors, self.config, self._on_param_changed,
            on_mod_engine=self._set_mod_engine_reg,
            on_vanilla=self._set_vanilla_reg,
            on_backup=self._create_backup,
            on_restore=self._restore_backup,
            parent=top_container
        )
        top_layout.addWidget(paths_card)
        self.active_reg_input = path_ctrls["active_regulation_path"]
        self.input_dir_input = path_ctrls["input_directory"]
        self.output_dir_input = path_ctrls["output_directory"]
        self.game_dir_input = path_ctrls["game_directory"]
        self.backup_btn = path_ctrls["backup_btn"]
        self.restore_btn = path_ctrls["restore_btn"]

        # Drop Rules and Diablo ARPG side-by-side layout
        rules_row = QHBoxLayout()
        rules_row.setSpacing(10)

        drop_card, drop_ctrls = ParamWidgetFactory.build_drop_style_card(
            descriptors, self.config, self._on_param_changed, parent=top_container
        )
        rules_row.addWidget(drop_card, stretch=1)
        self.addition_type_combo = drop_ctrls["addition_type"]
        self.anti_dup_combo = drop_ctrls["anti_dup"]
        self.mult_slider = drop_ctrls["global_multiplier_percent"]
        self.mult_label = drop_ctrls["mult_label"]

        diablo_card, diablo_ctrls = ParamWidgetFactory.build_diablo_card(
            descriptors, self.config, self._on_param_changed, parent=top_container
        )
        rules_row.addWidget(diablo_card, stretch=1)
        self.diablo_enabled_cb = diablo_ctrls["diablo_loot_enabled"]
        self.diablo_variants_spin = diablo_ctrls["diablo_variants_per_item"]
        self.diablo_seed_spin = diablo_ctrls["diablo_seed"]

        top_layout.addLayout(rules_row)
        self.top_scroll.setWidget(top_container)
        self.main_splitter.addWidget(self.top_scroll)

        # Bottom Section: Loot Modal Inspection Launcher & Action Bar
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(8)

        # Prominent Loot Inspection Card
        inspect_card = QFrame()
        inspect_card.setProperty("class", "card")
        inspect_layout = QHBoxLayout(inspect_card)
        inspect_layout.setContentsMargins(14, 14, 14, 14)
        inspect_layout.setSpacing(12)

        inspect_info_vbox = QVBoxLayout()
        self.loot_status_title = QLabel("📦 INJECTED LOOT & DROP TABLES")
        self.loot_status_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 13px;")
        inspect_info_vbox.addWidget(self.loot_status_title)

        self.loot_status_desc = QLabel("Inspect assigned enemy drop locations, customize % rates, or toggle mystery mode.")
        self.loot_status_desc.setStyleSheet("color: #ede8df; font-size: 12px;")
        inspect_info_vbox.addWidget(self.loot_status_desc)
        inspect_layout.addLayout(inspect_info_vbox, stretch=1)

        scan_btn = QPushButton("🔄 Scan Input Mods")
        scan_btn.clicked.connect(self._scan_mods)
        inspect_layout.addWidget(scan_btn)

        self.open_modal_btn = QPushButton("👁 Open Loot Distribution Modal")
        self.open_modal_btn.setProperty("class", "primary")
        self.open_modal_btn.setFixedHeight(36)
        self.open_modal_btn.clicked.connect(self._open_loot_modal)
        inspect_layout.addWidget(self.open_modal_btn)

        bottom_layout.addWidget(inspect_card)

        # Action Bar
        action_layout = QHBoxLayout()
        self.uninstall_btn = QPushButton("Rollback / Uninstall Injected Mods")
        self.uninstall_btn.setProperty("class", "danger")
        self.uninstall_btn.clicked.connect(self._uninstall_mods)
        action_layout.addWidget(self.uninstall_btn)
        action_layout.addStretch()

        self.forge_btn = QPushButton("Forge Standalone Gear & Inject Loot")
        self.forge_btn.setProperty("class", "primary")
        self.forge_btn.setFixedHeight(38)
        self.forge_btn.clicked.connect(self._forge_mods)
        action_layout.addWidget(self.forge_btn)

        bottom_layout.addLayout(action_layout)
        self.main_splitter.addWidget(bottom_container)
        self.main_splitter.setSizes([450, 180])
        main_layout.addWidget(self.main_splitter)

        # Developer Console Drawer
        self.console_drawer = QDialog(self)
        self.console_drawer.setWindowTitle("LootForge Developer Console")
        self.console_drawer.resize(600, 350)
        c_layout = QVBoxLayout(self.console_drawer)
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setStyleSheet("background-color: #07080a; color: #8ee3a4; font-family: monospace;")
        c_layout.addWidget(self.console_text)
        c_btns = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.console_text.clear)
        c_btns.addWidget(clear_btn)
        c_btns.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.console_drawer.hide)
        c_btns.addWidget(close_btn)
        c_layout.addLayout(c_btns)

    def _open_loot_modal(self):
        self._sync_modal_data()
        self.loot_modal.exec()

    def _sync_modal_data(self):
        self.loot_modal.set_data(
            drop_configs=self.drop_configs,
            global_multiplier=self.global_multiplier_percent,
            global_spoiled=self.global_spoiled,
            items_per_page=self.items_per_page,
            diablo_enabled=self.config.diablo_loot_enabled
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
        elif key == "diablo_loot_enabled":
            self._sync_modal_data()

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
        if self.banner_collapsed:
            self.banner_desc.hide()
            self.banner_toggle_btn.setText("▼ Expand Notice")
        else:
            self.banner_desc.show()
            self.banner_toggle_btn.setText("▲ Collapse Notice")
        self.config.banner_collapsed = self.banner_collapsed
        self.config.save(self.config_path)

    def _toggle_global_spoil(self):
        self.global_spoiled = not self.global_spoiled
        self.config.global_spoiled = self.global_spoiled
        self.config.save(self.config_path)
        self._sync_modal_data()

    def _toggle_dev_console(self):
        if self.console_drawer.isVisible():
            self.console_drawer.hide()
        else:
            self.console_drawer.show()

    def _load_initial_data(self):
        if not self.config.active_regulation_path:
            self.config.active_regulation_path = self.config.resolve_active_regulation_bin()
            if hasattr(self, "active_reg_input"):
                self.active_reg_input.setText(self.config.active_regulation_path)
        self._scan_mods()

    def _set_mod_engine_reg(self):
        out_p = Path(self.config.output_directory)
        if not out_p.is_absolute():
            out_p = self.base_dir / out_p
        mod_reg = str(out_p / "regulation.bin")
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
        import re as _re
        cleaned = _re.sub(r'-\d{2,}-[\d-]+$', '', folder_name).replace('_', ' ').replace('-', ' ')
        cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
        if cleaned == cleaned.lower():
            cleaned = cleaned.title()
        return f"✦ {cleaned} [LootForge]"

    def _scan_mods(self):
        try:
            input_p = Path(self.config.input_directory)
            if not input_p.is_absolute():
                input_p = self.base_dir / input_p
            self.scanned_sets = self.scanner.scan_directory(str(input_p))
            self.id_allocator.reset()
            self.drop_configs.clear()

            for s in self.scanned_sets:
                s.allocation = self.id_allocator.allocate(s.set_id)
                saved_user_rate = self.config.user_drop_rates.get(s.set_id, 20.0)
                saved_spoil = self.config.item_spoiled_states.get(s.set_id, False)
                self.drop_configs.append(ItemDropConfig(
                    item_key=s.set_id,
                    name=self._format_mod_display_name(s.folder_or_archive_name),
                    vanilla_rate=20.0,
                    user_rate=saved_user_rate,
                    is_spoiled=saved_spoil,
                    source_entity="Pending Route"
                ))

            self.summary_badge.setText(f"{len(self.scanned_sets)} Mod Sets Detected ({len(self.drop_configs)} Items)")
            self.open_modal_btn.setText(f"👁 Open Loot Distribution Modal ({len(self.drop_configs)} Items)")
            self._recalculate_distribution()
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Error scanning mods: {e}")

    def _recalculate_distribution(self):
        add_type = AdditionType(self.addition_type_combo.currentData()) if hasattr(self, "addition_type_combo") else AdditionType(self.config.addition_type)
        anti_dup = AntiDup(self.anti_dup_combo.currentData()) if hasattr(self, "anti_dup_combo") else AntiDup(self.config.anti_dup)

        self.config.addition_type = add_type.value
        self.config.anti_dup = anti_dup.value
        self.config.save(self.config_path)
        self.distributor.reset_rotation_state()

        for s, cfg in zip(self.scanned_sets, self.drop_configs):
            target = self.distributor.distribute_set(
                s, addition_type=add_type, anti_dup=anti_dup,
                global_rate_multiplier_percent=self.global_multiplier_percent
            )
            cfg.source_entity = target.display_name
            cfg.vanilla_rate = target.chance_or_cost

        self._sync_modal_data()

    def _on_user_rate_changed(self, cfg: ItemDropConfig, val: float):
        cfg.user_rate = val
        self.config.user_drop_rates[cfg.item_key] = val
        self.config.save(self.config_path)

    def _reset_item_rate(self, cfg: ItemDropConfig, spinbox: QDoubleSpinBox):
        cfg.user_rate = cfg.vanilla_rate
        if cfg.item_key in self.config.user_drop_rates:
            del self.config.user_drop_rates[cfg.item_key]
        self.config.save(self.config_path)
        spinbox.setValue(cfg.vanilla_rate)

    def _toggle_item_spoil(self, cfg: ItemDropConfig):
        cfg.is_spoiled = not cfg.is_spoiled
        self.config.item_spoiled_states[cfg.item_key] = cfg.is_spoiled
        self.config.save(self.config_path)

    def _create_backup(self):
        reg_path = self.active_reg_input.text().strip() or os.path.join(self.config.game_directory, "regulation.bin")
        try:
            if not Path(reg_path).exists():
                Path(reg_path).parent.mkdir(parents=True, exist_ok=True)
                with open(reg_path, "wb") as f:
                    f.write(b"ELDEN_RING_REGULATION_PLACEHOLDER")
            rec = self.backup_manager.create_backup(reg_path)
            QMessageBox.information(self, "Backup Created", f"Successfully created backup:\n{rec.backup_file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Failed to create backup: {e}")

    def _restore_backup(self):
        reg_path = self.active_reg_input.text().strip() or os.path.join(self.config.game_directory, "regulation.bin")
        reply = QMessageBox.question(self, "Confirm Restore", "Restore pristine regulation.bin from the latest backup?")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.backup_manager.restore_latest_backup(reg_path)
                QMessageBox.information(self, "Restore Complete", "Pristine regulation.bin restored successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Restore Error", f"Restore failed: {e}")

    def _forge_mods(self):
        if not self.scanned_sets:
            QMessageBox.warning(self, "No Mods", "No mod sets detected in input_mods to forge.")
            return

        self._recalculate_distribution()
        active_input = self.active_reg_input.text().strip()

        if self.config.game_directory:
            self.regulation_manager.backup_game_assets(self.config.game_directory)

        source_reg = self.regulation_manager.resolve_source_regulation(
            active_path=active_input, game_dir=self.config.game_directory, output_dir=self.config.output_directory
        )
        if not source_reg or not source_reg.exists():
            QMessageBox.critical(self, "Regulation Not Found", "Could not find a valid Elden Ring regulation.bin to read from!")
            return

        target_reg = self.regulation_manager.resolve_target_regulation(
            active_path=active_input, output_dir=self.config.output_directory, game_dir=self.config.game_directory
        )

        try:
            if target_reg.exists():
                self.backup_manager.create_backup(str(target_reg))

            patch_specs = []
            injected_count = 0
            diablo_total_variants = 0

            for s, cfg in zip(self.scanned_sets, self.drop_configs):
                if s.loot_target:
                    s.loot_target.chance_or_cost = self.distributor.calculate_final_rate(
                        cfg.user_rate, self.global_multiplier_percent
                    )

                input_p = Path(self.config.input_directory)
                if not input_p.is_absolute():
                    input_p = self.base_dir / input_p
                staged = self.asset_renumberer.stage_mod_set(str(input_p), s)

                base_spec = self.param_builder.build_patch_spec(s)
                if self.config.diablo_loot_enabled and self.config.diablo_variants_per_item > 1:
                    from src.diablo_generator import DiabloLootGenerator
                    diablo_gen = DiabloLootGenerator(seed=self.config.diablo_seed)
                    variants = diablo_gen.generate_variants_for_spec(
                        base_spec, variants_per_item=self.config.diablo_variants_per_item
                    )
                    patch_specs.extend(variants)
                    diablo_total_variants += len(variants)
                else:
                    patch_specs.append(base_spec)

                self.manifest_store.record_set(s, staged)
                injected_count += 1

            patch_result = self.regulation_manager.execute_patch(
                specs=patch_specs, source_reg=source_reg, target_reg=target_reg, game_dir=self.config.game_directory
            )

            output_dir = target_reg.parent
            input_dir = Path(self.config.input_directory)
            if not input_dir.is_absolute():
                input_dir = self.base_dir / input_dir
            parts_deployed = self.regulation_manager.deploy_parts(
                mod_sets=self.scanned_sets, input_base_dir=input_dir, output_dir=output_dir
            )

            self.active_reg_input.setText(str(target_reg))
            self.config.active_regulation_path = str(target_reg)
            self.config.save(self.config_path)

            file_size_mb = round(patch_result["target_size_bytes"] / (1024 * 1024), 2)
            diablo_info = f"⚡ Diablo ARPG: {diablo_total_variants} procedural relics generated!\n" if diablo_total_variants > 0 else ""
            msg = (
                f"Successfully forged and injected {injected_count} standalone mod set(s)!\n\n"
                f"{diablo_info}"
                f"✅ Regulation: '{target_reg}' ({file_size_mb} MB)\n"
                f"✅ Parts Deployed: {parts_deployed} files to {output_dir / 'parts'}\n\n"
                f"Ready to launch with Mod Engine 2 or your mod manager!"
            )
            QMessageBox.information(self, "Forge Complete", msg)
        except Exception as e:
            system_logger.error(f"Forge failed: {e}", source="Forge")
            QMessageBox.critical(self, "Forge Error", f"Forge failed: {e}")

    def _uninstall_mods(self):
        reply = QMessageBox.question(self, "Confirm Rollback", "Uninstall all staged standalone mods and revert manifest?")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for rec in self.manifest_store.get_all_records():
                    self.asset_renumberer.cleanup_files(rec.staged_files)
                self.manifest_store.clear()
                QMessageBox.information(self, "Rollback Complete", "All injected mods have been cleanly uninstalled.")
                self._scan_mods()
            except Exception as e:
                QMessageBox.critical(self, "Rollback Error", f"Uninstall failed: {e}")

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
