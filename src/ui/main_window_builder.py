"""
Main Window Layout Builder for LootForge Qt GUI.
Constructs widgets, cards, and dev console drawers.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import Any
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QScrollArea, QSplitter, QTextEdit, QDialog
    )
    from PySide6.QtCore import Qt
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QScrollArea, QSplitter, QTextEdit, QDialog
    )
    from PyQt6.QtCore import Qt

from src.ui.param_schema import get_generator_param_descriptors
from src.ui.param_widget_factory import ParamWidgetFactory
from src.ui.multipliers_widget_factory import MultipliersWidgetFactory


class MainWindowBuilder:
    """
    Constructs the GUI widgets and layout for LootForgeMainWindow.
    """

    @classmethod
    def build_main_ui(cls, window: Any) -> None:
        """Constructs layout hierarchy and sets controls onto window."""
        main_widget = QWidget()
        window.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title_label = QLabel("LOOTFORGE: ELDEN RING RELIC INJECTOR")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffd475; letter-spacing: 1.5px;")
        header.addWidget(title_label)

        window.summary_badge = QLabel("0 Mod Sets Detected")
        window.summary_badge.setStyleSheet(
            "background-color: #161924; color: #c5a059; border: 1px solid rgba(197, 160, 89, 0.35); "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        header.addWidget(window.summary_badge)
        header.addStretch()

        window.banner_toggle_btn = QPushButton("▲ Collapse Notice")
        window.banner_toggle_btn.clicked.connect(window._toggle_banner)
        header.addWidget(window.banner_toggle_btn)

        window.dev_console_btn = QPushButton("⚙ Dev Console")
        window.dev_console_btn.clicked.connect(window._toggle_dev_console)
        header.addWidget(window.dev_console_btn)
        main_layout.addLayout(header)

        # Splitter Layout
        window.main_splitter = QSplitter(Qt.Orientation.Vertical)
        window.main_splitter.setChildrenCollapsible(False)
        window.main_splitter.setHandleWidth(8)

        # Scrollable Configuration Container
        window.top_scroll = QScrollArea()
        window.top_scroll.setWidgetResizable(True)
        window.top_scroll.setFrameShape(QFrame.Shape.NoFrame)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 4, 0)
        top_layout.setSpacing(10)

        # Banner Frame
        window.banner_frame = QFrame()
        window.banner_frame.setProperty("class", "banner")
        banner_vbox = QVBoxLayout(window.banner_frame)
        banner_vbox.setContentsMargins(12, 10, 12, 10)
        banner_title = QLabel("⚠️ USING MOD ENGINE 2 OR A MOD MANAGER? READ THIS FIRST:")
        banner_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 13px;")
        banner_vbox.addWidget(banner_title)
        window.banner_desc = QLabel(
            "Always point to your CURRENT ACTIVE regulation.bin (such as mod/regulation.bin or your profile).\n"
            "LootForge injects standalone items and loot drops directly so all other mods stay 100% intact!"
        )
        window.banner_desc.setWordWrap(True)
        window.banner_desc.setStyleSheet("color: #ede8df; line-height: 1.4;")
        banner_vbox.addWidget(window.banner_desc)
        top_layout.addWidget(window.banner_frame)
        if window.banner_collapsed:
            window.banner_desc.hide()
            window.banner_toggle_btn.setText("▼ Expand Notice")

        # Schema-driven auto-generated parameter cards
        descriptors = get_generator_param_descriptors()

        # Paths Card
        paths_card, path_ctrls = ParamWidgetFactory.build_paths_card(
            descriptors, window.config, window._on_param_changed,
            on_mod_engine=window._set_mod_engine_reg,
            on_vanilla=window._set_vanilla_reg,
            on_backup=window._create_backup,
            on_restore=window._restore_backup,
            parent=top_container
        )
        top_layout.addWidget(paths_card)
        window.active_reg_input = path_ctrls["active_regulation_path"]
        window.input_dir_input = path_ctrls["input_directory"]
        window.output_dir_input = path_ctrls["output_directory"]
        window.game_dir_input = path_ctrls["game_directory"]
        window.backup_btn = path_ctrls["backup_btn"]
        window.restore_btn = path_ctrls["restore_btn"]

        # Drop Rules and Diablo ARPG side-by-side layout
        rules_row = QHBoxLayout()
        rules_row.setSpacing(10)

        drop_card, drop_ctrls = ParamWidgetFactory.build_drop_style_card(
            descriptors, window.config, window._on_param_changed, parent=top_container
        )
        rules_row.addWidget(drop_card, stretch=1)
        window.addition_type_combo = drop_ctrls["addition_type"]
        window.anti_dup_combo = drop_ctrls["anti_dup"]
        window.mult_slider = drop_ctrls["global_multiplier_percent"]
        window.mult_label = drop_ctrls["mult_label"]

        diablo_card, diablo_ctrls = ParamWidgetFactory.build_diablo_card(
            descriptors, window.config, window._on_param_changed, parent=top_container
        )
        rules_row.addWidget(diablo_card, stretch=1)
        window.diablo_enabled_cb = diablo_ctrls["diablo_loot_enabled"]
        window.diablo_variants_spin = diablo_ctrls["diablo_variants_per_item"]
        window.diablo_seed_spin = diablo_ctrls["diablo_seed"]

        top_layout.addLayout(rules_row)

        multipliers_card, mult_ctrls = MultipliersWidgetFactory.build_multipliers_card(
            window.config, window._on_param_changed, parent=top_container
        )
        top_layout.addWidget(multipliers_card)
        window.master_multiplier_slider = mult_ctrls["master_multiplier"]
        window.stats_multiplier_slider = mult_ctrls["stats_multiplier"]
        window.price_multiplier_slider = mult_ctrls["price_multiplier"]
        window.master_multiplier_label = mult_ctrls["master_label"]
        window.stats_multiplier_label = mult_ctrls["stats_label"]
        window.price_multiplier_label = mult_ctrls["price_label"]

        window.top_scroll.setWidget(top_container)
        window.main_splitter.addWidget(window.top_scroll)

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
        window.loot_status_title = QLabel("📦 INJECTED LOOT & DROP TABLES")
        window.loot_status_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 13px;")
        inspect_info_vbox.addWidget(window.loot_status_title)

        window.loot_status_desc = QLabel("Inspect assigned enemy drop locations, customize % rates, or toggle mystery mode.")
        window.loot_status_desc.setStyleSheet("color: #ede8df; font-size: 12px;")
        inspect_info_vbox.addWidget(window.loot_status_desc)
        inspect_layout.addLayout(inspect_info_vbox, stretch=1)

        scan_btn = QPushButton("🔄 Scan Input Mods")
        scan_btn.clicked.connect(window._scan_mods)
        inspect_layout.addWidget(scan_btn)

        window.open_modal_btn = QPushButton("👁 Open Loot Distribution Modal")
        window.open_modal_btn.setProperty("class", "primary")
        window.open_modal_btn.setFixedHeight(36)
        window.open_modal_btn.clicked.connect(window._open_loot_modal)
        inspect_layout.addWidget(window.open_modal_btn)

        bottom_layout.addWidget(inspect_card)

        # Action Bar
        action_layout = QHBoxLayout()
        window.uninstall_btn = QPushButton("Rollback / Uninstall Injected Mods")
        window.uninstall_btn.setProperty("class", "danger")
        window.uninstall_btn.clicked.connect(window._uninstall_mods)
        action_layout.addWidget(window.uninstall_btn)
        action_layout.addStretch()

        window.forge_btn = QPushButton("Forge Standalone Gear & Inject Loot")
        window.forge_btn.setProperty("class", "primary")
        window.forge_btn.setFixedHeight(38)
        window.forge_btn.clicked.connect(window._forge_mods)
        action_layout.addWidget(window.forge_btn)

        bottom_layout.addLayout(action_layout)
        window.main_splitter.addWidget(bottom_container)
        window.main_splitter.setSizes([450, 180])
        main_layout.addWidget(window.main_splitter)

        # Developer Console Drawer
        window.console_drawer = QDialog(window)
        window.console_drawer.setWindowTitle("LootForge Developer Console")
        window.console_drawer.resize(600, 350)
        c_layout = QVBoxLayout(window.console_drawer)
        window.console_text = QTextEdit()
        window.console_text.setReadOnly(True)
        window.console_text.setStyleSheet("background-color: #07080a; color: #8ee3a4; font-family: monospace;")
        c_layout.addWidget(window.console_text)
        c_btns = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(window.console_text.clear)
        c_btns.addWidget(clear_btn)
        c_btns.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(window.console_drawer.hide)
        c_btns.addWidget(close_btn)
        c_layout.addLayout(c_btns)
