"""
PyQt6 / PySide6 Desktop GUI for LootForge.

Features:
- Dark Souls fantasy theme with gold accents and responsive layout
- Prominent Mod Manager warning banner
- AdditionType and AntiDup Enum controls
- Set invariance enforcement (pieces from the same mod drop from the same mob)
- Global drop rate multiplier governed by 100% (1*)
- Paginated drop rate tuning table with color-coded rates (Red < default, Grey == default, Green > default)
- Global and individual Mystery / Spoiler protection
- Floating real-time Developer Console drawer [CS-DEBUG]
"""

import sys
import os
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

# Cross-platform Qt binding (PySide6 official, fallback to PyQt6)
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QFileDialog, QTableWidget,
        QTableWidgetItem, QHeaderView, QComboBox, QDoubleSpinBox,
        QSlider, QCheckBox, QFrame, QScrollArea, QMessageBox,
        QProgressBar, QTextEdit, QDialog, QSplitter, QSizePolicy
    )
    from PySide6.QtCore import Qt, QTimer, Signal as pyqtSignal
    from PySide6.QtGui import QFont, QColor, QPalette, QIcon
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QFileDialog, QTableWidget,
        QTableWidgetItem, QHeaderView, QComboBox, QDoubleSpinBox,
        QSlider, QCheckBox, QFrame, QScrollArea, QMessageBox,
        QProgressBar, QTextEdit, QDialog, QSplitter, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

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


# Dark Souls QSS Stylesheet
DARK_SOULS_QSS = """
QMainWindow, QWidget {
    background-color: #0c0d12;
    color: #ede8df;
    font-family: "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QSplitter::handle:vertical {
    background-color: #1a1e2b;
    border: 1px solid rgba(197, 160, 89, 0.4);
    border-radius: 3px;
    height: 7px;
    margin: 2px 25px;
}

QSplitter::handle:vertical:hover {
    background-color: #c5a059;
    border: 1px solid #ffd475;
}

QFrame.banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(197, 160, 89, 0.15), stop:1 rgba(18, 20, 28, 0.95));
    border: 1px solid #ffd475;
    border-left: 5px solid #ffd475;
    border-radius: 8px;
    padding: 12px;
}

QFrame.card {
    background-color: rgba(18, 20, 28, 0.85);
    border: 1px solid rgba(197, 160, 89, 0.35);
    border-radius: 8px;
    padding: 14px;
}

QLabel.title {
    font-size: 22px;
    font-weight: bold;
    color: #ffd475;
    letter-spacing: 2px;
}

QLabel.section-header {
    font-size: 15px;
    font-weight: bold;
    color: #c5a059;
}

QLineEdit, QComboBox, QDoubleSpinBox {
    background-color: #07080a;
    border: 1px solid rgba(197, 160, 89, 0.4);
    border-radius: 4px;
    padding: 6px 10px;
    color: #ede8df;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #ffd475;
}

QPushButton {
    background-color: #1a1e2b;
    border: 1px solid rgba(197, 160, 89, 0.4);
    border-radius: 4px;
    padding: 7px 14px;
    color: #ede8df;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #262c3e;
    border: 1px solid #ffd475;
}

QPushButton.primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #c5a059, stop:1 #8c6e32);
    color: #0c0d12;
    font-weight: bold;
    border: 1px solid #ffd475;
}

QPushButton.primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #dfba73, stop:1 #a8853f);
}

QPushButton.danger {
    background-color: rgba(224, 82, 82, 0.15);
    border: 1px solid rgba(224, 82, 82, 0.5);
    color: #ff8585;
}

QPushButton.danger:hover {
    background-color: rgba(224, 82, 82, 0.3);
    border: 1px solid #ff5252;
}

QTableWidget {
    background-color: #08090c;
    border: 1px solid rgba(197, 160, 89, 0.3);
    gridline-color: rgba(197, 160, 89, 0.15);
    selection-background-color: rgba(197, 160, 89, 0.2);
}

QHeaderView::section {
    background-color: #12141c;
    color: #c5a059;
    padding: 8px;
    border: 1px solid rgba(197, 160, 89, 0.2);
    font-weight: bold;
}

QScrollBar:vertical {
    background: #08090c;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #c5a059;
    border-radius: 4px;
}

QScrollBar:horizontal {
    background: #08090c;
    height: 10px;
}

QScrollBar::handle:horizontal {
    background: #c5a059;
    border-radius: 4px;
}
"""


class LootForgeMainWindow(QMainWindow):
    """
    Main Qt Window for LootForge.
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
        self.param_builder = ParamBuilder()
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

        # State restored from config
        self.scanned_sets: List[DetectedModSet] = []
        self.drop_configs: List[ItemDropConfig] = []
        self.current_page: int = 1
        self.items_per_page: int = getattr(self.config, "items_per_page", 8)
        self.global_multiplier_percent: float = getattr(self.config, "global_multiplier_percent", 100.0)
        self.global_spoiled: bool = getattr(self.config, "global_spoiled", True)
        self.banner_collapsed: bool = getattr(self.config, "banner_collapsed", False)

        self.setWindowTitle("LootForge: Elden Ring Relic & Loot Injector (Qt Edition)")
        self.resize(1150, 850)
        self.setMinimumSize(850, 520)
        self.setStyleSheet(DARK_SOULS_QSS)

        self._build_ui()
        self._load_initial_data()

        # Timer for developer console log polling
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._poll_logs)
        self.log_timer.start(1500)

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # 1. Header (Compact & Responsive)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_label = QLabel("LOOTFORGE: ELDEN RING RELIC INJECTOR")
        title_label.setProperty("class", "title")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffd475; letter-spacing: 1.5px;")
        header_layout.addWidget(title_label)

        self.summary_badge = QLabel("0 Mod Sets Detected")
        self.summary_badge.setStyleSheet(
            "background-color: #161924; color: #c5a059; border: 1px solid rgba(197, 160, 89, 0.35); "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        header_layout.addWidget(self.summary_badge)

        header_layout.addStretch()

        self.banner_toggle_btn = QPushButton("▲ Collapse Notice")
        self.banner_toggle_btn.clicked.connect(self._toggle_banner)
        header_layout.addWidget(self.banner_toggle_btn)

        self.dev_console_btn = QPushButton("⚙ Dev Console")
        self.dev_console_btn.clicked.connect(self._toggle_dev_console)
        header_layout.addWidget(self.dev_console_btn)

        main_layout.addLayout(header_layout)

        # Main Vertical Splitter for dynamic full-screen scaling and custom pane sizing
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)

        # Top Section: Scrollable Configuration Container
        self.top_scroll = QScrollArea()
        self.top_scroll.setWidgetResizable(True)
        self.top_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.top_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.top_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 4, 0)
        top_layout.setSpacing(10)

        # 2. Prominent Mod Manager Banner
        self.banner_frame = QFrame()
        self.banner_frame.setProperty("class", "banner")
        banner_layout = QVBoxLayout(self.banner_frame)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(6)

        banner_title = QLabel("⚠️ USING MOD ENGINE 2 OR A MOD MANAGER? READ THIS FIRST:")
        banner_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 13px;")
        banner_layout.addWidget(banner_title)

        self.banner_desc = QLabel(
            "Always point to your CURRENT ACTIVE regulation.bin (such as mod/regulation.bin or your Mod Manager's active profile).\n"
            "LootForge will inject standalone items and loot drops directly into your existing modded file so all your current mods, movesets, and balance changes stay 100% intact!"
        )
        self.banner_desc.setWordWrap(True)
        self.banner_desc.setStyleSheet("color: #ede8df; line-height: 1.4;")
        banner_layout.addWidget(self.banner_desc)
        top_layout.addWidget(self.banner_frame)

        if self.banner_collapsed:
            self.banner_desc.hide()
            self.banner_toggle_btn.setText("▼ Expand Notice")

        # 3. Active Regulation & Path Configuration Card
        paths_card = QFrame()
        paths_card.setProperty("class", "card")
        paths_layout = QVBoxLayout(paths_card)
        paths_layout.setContentsMargins(12, 12, 12, 12)
        paths_layout.setSpacing(8)

        # Active regulation.bin file picker
        paths_row1 = QHBoxLayout()
        paths_row1.addWidget(QLabel("Active regulation.bin:"), stretch=0)
        self.active_reg_input = QLineEdit()
        self.active_reg_input.setPlaceholderText("e.g. mod/regulation.bin or Game/regulation.bin")
        self.active_reg_input.setText(self.config.active_regulation_path)
        self.active_reg_input.textChanged.connect(self._on_reg_path_changed)
        paths_row1.addWidget(self.active_reg_input, stretch=1)

        browse_reg_btn = QPushButton("📄 Browse File...")
        browse_reg_btn.clicked.connect(self._browse_regulation_file)
        paths_row1.addWidget(browse_reg_btn)
        paths_layout.addLayout(paths_row1)

        # Mod Input Directory Picker
        paths_row2 = QHBoxLayout()
        paths_row2.addWidget(QLabel("Mod Input Folder:"), stretch=0)
        self.input_dir_input = QLineEdit()
        self.input_dir_input.setText(self.config.input_directory)
        self.input_dir_input.textChanged.connect(self._on_input_dir_changed)
        paths_row2.addWidget(self.input_dir_input, stretch=1)

        browse_input_btn = QPushButton("📁 Browse Folder...")
        browse_input_btn.clicked.connect(self._browse_input_folder)
        paths_row2.addWidget(browse_input_btn)
        paths_layout.addLayout(paths_row2)

        # Mod Output / ModEngine2 Staging Directory Picker
        paths_row3 = QHBoxLayout()
        paths_row3.addWidget(QLabel("Mod Output Folder:"), stretch=0)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setText(self.config.output_directory)
        self.output_dir_input.textChanged.connect(self._on_output_dir_changed)
        paths_row3.addWidget(self.output_dir_input, stretch=1)

        browse_output_btn = QPushButton("📁 Browse Folder...")
        browse_output_btn.clicked.connect(self._browse_output_folder)
        paths_row3.addWidget(browse_output_btn)
        paths_layout.addLayout(paths_row3)

        # Elden Ring Game Installation Directory Picker
        paths_row4 = QHBoxLayout()
        paths_row4.addWidget(QLabel("Game Directory:"), stretch=0)
        self.game_dir_input = QLineEdit()
        self.game_dir_input.setText(self.config.game_directory)
        self.game_dir_input.textChanged.connect(self._on_game_dir_changed)
        paths_row4.addWidget(self.game_dir_input, stretch=1)

        browse_game_btn = QPushButton("📁 Browse Folder...")
        browse_game_btn.clicked.connect(self._browse_game_folder)
        paths_row4.addWidget(browse_game_btn)
        paths_layout.addLayout(paths_row4)

        # Path helper buttons
        btns_row = QHBoxLayout()
        btns_row.setSpacing(8)
        use_mod_btn = QPushButton("Use Mod Engine (mod/regulation.bin)")
        use_mod_btn.clicked.connect(self._set_mod_engine_reg)
        btns_row.addWidget(use_mod_btn)

        use_vanilla_btn = QPushButton("Use Vanilla Game Regulation")
        use_vanilla_btn.clicked.connect(self._set_vanilla_reg)
        btns_row.addWidget(use_vanilla_btn)

        btns_row.addStretch()

        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.clicked.connect(self._create_backup)
        btns_row.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore Latest Backup")
        self.restore_btn.clicked.connect(self._restore_backup)
        btns_row.addWidget(self.restore_btn)
        paths_layout.addLayout(btns_row)

        top_layout.addWidget(paths_card)

        # 4. Mode Selection (Enums: AdditionType & AntiDup) + Global Multiplier
        modes_card = QFrame()
        modes_card.setProperty("class", "card")
        modes_layout = QHBoxLayout(modes_card)
        modes_layout.setContentsMargins(12, 10, 12, 10)
        modes_layout.setSpacing(14)

        # Addition Type Enum
        add_type_vbox = QVBoxLayout()
        add_type_vbox.setSpacing(4)
        add_type_vbox.addWidget(QLabel("<b>Addition Type (Enum)</b>:"))
        self.addition_type_combo = QComboBox()
        self.addition_type_combo.addItem("[1] Random Addition (Mobs / Non-dropped to Bosses & Shops)", AdditionType.RANDOM_ADDITION)
        self.addition_type_combo.addItem("[2] Standard Addition (Thematic Expected Drop / Shop)", AdditionType.STANDARD_ADDITION)
        self.addition_type_combo.addItem("[3] Test Mode (Distribute Across All Loot Pools for Verification)", AdditionType.TEST_MODE)
        init_add_val = getattr(self.config, "addition_type", 2)
        init_add_idx = self.addition_type_combo.findData(AdditionType(init_add_val))
        self.addition_type_combo.setCurrentIndex(init_add_idx if init_add_idx >= 0 else 1)
        self.addition_type_combo.currentIndexChanged.connect(self._recalculate_distribution)
        add_type_vbox.addWidget(self.addition_type_combo)
        modes_layout.addLayout(add_type_vbox, stretch=1)

        # Anti Dup Enum (for 100% Drops)
        anti_dup_vbox = QVBoxLayout()
        anti_dup_vbox.setSpacing(4)
        anti_dup_vbox.addWidget(QLabel("<b>Anti-Dup for 100% Drops (Enum)</b>:"))
        self.anti_dup_combo = QComboBox()
        self.anti_dup_combo.addItem("[1] Boss Rotation (Max 1/Boss -> Mini-Bosses -> Wild)", AntiDup.BOSS_ROTATION)
        self.anti_dup_combo.addItem("[2] Everything Goes in Wild at Normal Rates", AntiDup.EVERYTHING_IN_THE_WILD)
        init_ad_val = getattr(self.config, "anti_dup", 1)
        init_ad_idx = self.anti_dup_combo.findData(AntiDup(init_ad_val))
        self.anti_dup_combo.setCurrentIndex(init_ad_idx if init_ad_idx >= 0 else 0)
        self.anti_dup_combo.currentIndexChanged.connect(self._recalculate_distribution)
        anti_dup_vbox.addWidget(self.anti_dup_combo)
        modes_layout.addLayout(anti_dup_vbox, stretch=1)

        # Global Multiplier (Governed by 100% / 1*)
        mult_vbox = QVBoxLayout()
        mult_vbox.setSpacing(4)
        init_mult = int(self.global_multiplier_percent)
        ratio = round(init_mult / 100.0, 2)
        self.mult_label = QLabel(f"<b>Global Multiplier</b>: {init_mult}% ({ratio}x)")
        mult_vbox.addWidget(self.mult_label)

        mult_controls = QHBoxLayout()
        mult_controls.setSpacing(8)
        self.mult_slider = QSlider(Qt.Orientation.Horizontal)
        self.mult_slider.setRange(10, 300)
        self.mult_slider.setValue(init_mult)
        self.mult_slider.valueChanged.connect(self._on_multiplier_changed)
        mult_controls.addWidget(self.mult_slider, stretch=1)

        reset_mult_btn = QPushButton("Reset 100%")
        reset_mult_btn.clicked.connect(lambda: self.mult_slider.setValue(100))
        mult_controls.addWidget(reset_mult_btn)

        mult_vbox.addLayout(mult_controls)
        modes_layout.addLayout(mult_vbox, stretch=1)

        top_layout.addWidget(modes_card)
        self.top_scroll.setWidget(top_container)

        self.main_splitter.addWidget(self.top_scroll)

        # Bottom Section: Table & Actions Container
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(8)

        # 5. Mystery / Spoiler Controls & Paginated Drop Rate Tuning Table
        table_card = QFrame()
        table_card.setProperty("class", "card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)

        table_header = QHBoxLayout()
        table_title = QLabel("<b>Drop Rates & Placement Configuration</b>")
        table_title.setStyleSheet("font-size: 14px; color: #ffd475;")
        table_header.addWidget(table_title)

        table_header.addStretch()

        # Dynamic page size selector for large displays / fullscreen scaling
        page_size_label = QLabel("Show:")
        page_size_label.setStyleSheet("color: #c5a059;")
        table_header.addWidget(page_size_label)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItem("8 items", 8)
        self.page_size_combo.addItem("15 items", 15)
        self.page_size_combo.addItem("25 items", 25)
        self.page_size_combo.addItem("50 items", 50)
        self.page_size_combo.addItem("All items", -1)
        init_page_idx = self.page_size_combo.findData(self.items_per_page)
        if init_page_idx >= 0:
            self.page_size_combo.setCurrentIndex(init_page_idx)
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        table_header.addWidget(self.page_size_combo)

        self.global_spoil_btn = QPushButton("🔒 Enable Mystery Mode" if self.global_spoiled else "👁 Reveal All Locations")
        self.global_spoil_btn.setToolTip("Hide all enemy/boss drop locations behind mystery placeholders" if self.global_spoiled else "Show all enemy/boss drop locations")
        self.global_spoil_btn.clicked.connect(self._toggle_global_spoil)
        table_header.addWidget(self.global_spoil_btn)

        scan_btn = QPushButton("🔄 Scan Input Mods")
        scan_btn.clicked.connect(self._scan_mods)
        table_header.addWidget(scan_btn)

        table_layout.addLayout(table_header)

        # The Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(7)
        self.items_table.setHorizontalHeaderLabels([
            "Mod / Item", "Location", "Vanilla %", "Configured %", "Final %", "Reset", "Reveal"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.items_table.setMinimumHeight(140)
        table_layout.addWidget(self.items_table)

        # Pagination controls
        pagination_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("◀ Previous Page")
        self.prev_page_btn.clicked.connect(self._prev_page)
        pagination_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("color: #ede8df; font-weight: 500;")
        pagination_layout.addWidget(self.page_label, stretch=1)

        self.next_page_btn = QPushButton("Next Page ▶")
        self.next_page_btn.clicked.connect(self._next_page)
        pagination_layout.addWidget(self.next_page_btn)

        table_layout.addLayout(pagination_layout)
        bottom_layout.addWidget(table_card, stretch=1)

        # 6. Action Bar
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

        # Splitter sizing & ratios:
        # Give ~310px to config on top, and allow bottom table pane to expand fully
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([310, 480])

        main_layout.addWidget(self.main_splitter)

        # 7. Floating Developer Console Drawer
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

    def _load_initial_data(self):
        # Auto-detect active regulation path
        if not self.config.active_regulation_path:
            self.config.active_regulation_path = self.config.resolve_active_regulation_bin()
            self.active_reg_input.setText(self.config.active_regulation_path)

        if self.config.input_directory:
            self.input_dir_input.setText(self.config.input_directory)
        if self.config.output_directory:
            self.output_dir_input.setText(self.config.output_directory)
        if self.config.game_directory:
            self.game_dir_input.setText(self.config.game_directory)

        self._scan_mods()

    def _browse_regulation_file(self):
        start_dir = self.config.game_directory if self.config.game_directory and Path(self.config.game_directory).exists() else str(self.base_dir)
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Active regulation.bin", start_dir, "Regulation Files (*.bin);;All Files (*)"
        )
        if file_path:
            self.active_reg_input.setText(file_path)
            self.config.active_regulation_path = file_path
            self.config.save(self.config_path)
            system_logger.info(f"User selected active regulation.bin: {file_path}", source="GUI")

    def _browse_input_folder(self):
        start_dir = self.config.input_directory
        if not Path(start_dir).is_absolute():
            start_dir = str(self.base_dir / start_dir)
        if not Path(start_dir).exists():
            start_dir = str(self.base_dir)

        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Mod Input Folder (contains raw replacement mods)", start_dir
        )
        if folder_path:
            self.input_dir_input.setText(folder_path)
            self.config.input_directory = folder_path
            self.config.save(self.config_path)
            system_logger.info(f"User changed Mod Input Folder to: {folder_path}", source="GUI")
            self._scan_mods()

    def _browse_output_folder(self):
        start_dir = self.config.output_directory
        if not Path(start_dir).is_absolute():
            start_dir = str(self.base_dir / start_dir)
        if not Path(start_dir).exists():
            start_dir = str(self.base_dir)

        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Mod Output Staging Folder (e.g. Mod Engine 2 'mod' folder)", start_dir
        )
        if folder_path:
            self.output_dir_input.setText(folder_path)
            self.config.output_directory = folder_path
            out_p = Path(folder_path)
            if not out_p.is_absolute():
                out_p = self.base_dir / out_p
            self.asset_renumberer.output_dir = out_p
            self.config.save(self.config_path)
            system_logger.info(f"User changed Mod Output Folder to: {folder_path}", source="GUI")

    def _browse_game_folder(self):
        start_dir = self.config.game_directory if self.config.game_directory and Path(self.config.game_directory).exists() else str(self.base_dir)
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Elden Ring Game Installation Folder (containing eldenring.exe)", start_dir
        )
        if folder_path:
            self.game_dir_input.setText(folder_path)
            self.config.game_directory = folder_path
            self.config.save(self.config_path)
            system_logger.info(f"User changed Elden Ring Game Folder to: {folder_path}", source="GUI")

            vanilla_reg = os.path.join(folder_path, "regulation.bin")
            if not self.config.active_regulation_path and Path(vanilla_reg).exists():
                self.active_reg_input.setText(vanilla_reg)
                self.config.active_regulation_path = vanilla_reg
                self.config.save(self.config_path)

    def _on_input_dir_changed(self, text: str):
        val = text.strip()
        if val != self.config.input_directory:
            self.config.input_directory = val
            self.config.save(self.config_path)

    def _on_output_dir_changed(self, text: str):
        val = text.strip()
        if val != self.config.output_directory:
            self.config.output_directory = val
            out_p = Path(val)
            if not out_p.is_absolute():
                out_p = self.base_dir / out_p
            self.asset_renumberer.output_dir = out_p
            self.config.save(self.config_path)

    def _on_game_dir_changed(self, text: str):
        val = text.strip()
        if val != self.config.game_directory:
            self.config.game_directory = val
            self.config.save(self.config_path)

    def _set_mod_engine_reg(self):
        out_p = Path(self.config.output_directory)
        if not out_p.is_absolute():
            out_p = self.base_dir / out_p
        mod_reg = str(out_p / "regulation.bin")
        self.active_reg_input.setText(mod_reg)
        self.config.active_regulation_path = mod_reg
        self.config.save(self.config_path)
        system_logger.info(f"Targeting Mod Engine regulation.bin: {mod_reg}", source="GUI")

    def _set_vanilla_reg(self):
        if self.config.game_directory:
            vanilla_reg = os.path.join(self.config.game_directory, "regulation.bin")
            self.active_reg_input.setText(vanilla_reg)
            self.config.active_regulation_path = vanilla_reg
            self.config.save(self.config_path)
            system_logger.info(f"Targeting Vanilla regulation.bin: {vanilla_reg}", source="GUI")

    def _on_reg_path_changed(self, text: str):
        self.config.active_regulation_path = text.strip()
        self.config.save(self.config_path)

    def _on_multiplier_changed(self, val: int):
        self.global_multiplier_percent = float(val)
        self.config.global_multiplier_percent = float(val)
        self.config.save(self.config_path)
        ratio = round(val / 100.0, 2)
        self.mult_label.setText(f"<b>Global Multiplier</b>: {val}% ({ratio}x)")
        self._render_table_page()

    def _toggle_banner(self):
        if not self.banner_desc.isHidden():
            self.banner_desc.hide()
            self.banner_toggle_btn.setText("▼ Expand Notice")
            self.banner_collapsed = True
        else:
            self.banner_desc.show()
            self.banner_toggle_btn.setText("▲ Collapse Notice")
            self.banner_collapsed = False
        self.config.banner_collapsed = self.banner_collapsed
        self.config.save(self.config_path)

    def _on_page_size_changed(self):
        data = self.page_size_combo.currentData()
        if data == -1:
            self.items_per_page = max(1, len(self.drop_configs)) if self.drop_configs else 8
        else:
            self.items_per_page = int(data)
        self.config.items_per_page = int(data)
        self.config.save(self.config_path)
        self.current_page = 1
        self._render_table_page()

    def _toggle_global_spoil(self):
        self.global_spoiled = not self.global_spoiled
        self.config.global_spoiled = self.global_spoiled
        self.config.save(self.config_path)
        if self.global_spoiled:
            self.global_spoil_btn.setText("🔒 Enable Mystery Mode")
            self.global_spoil_btn.setToolTip("Hide all enemy/boss drop locations behind mystery placeholders")
        else:
            self.global_spoil_btn.setText("👁 Reveal All Locations")
            self.global_spoil_btn.setToolTip("Show all enemy/boss drop locations")
        self._render_table_page()

    @staticmethod
    def _format_mod_display_name(folder_name: str) -> str:
        """Derives a clean display name from the mod folder name with LootForge annotation."""
        import re as _re
        # Remove common Nexus/version suffixes like -1634-1-0-1656336866
        cleaned = _re.sub(r'-\d{2,}-[\d-]+$', '', folder_name)
        # Replace underscores and hyphens with spaces
        cleaned = cleaned.replace('_', ' ').replace('-', ' ')
        # Collapse multiple spaces
        cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
        # Title-case if all lowercase
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
                alloc = self.id_allocator.allocate(s.set_id)
                s.allocation = alloc

                # Default config entry
                vanilla_rate = 20.0
                # Use mod folder name instead of vanilla target name,
                # with annotation per design doc
                display_name = self._format_mod_display_name(s.folder_or_archive_name)
                saved_user_rate = self.config.user_drop_rates.get(s.set_id, vanilla_rate)
                saved_spoil = self.config.item_spoiled_states.get(s.set_id, False)
                cfg = ItemDropConfig(
                    item_key=s.set_id,
                    name=display_name,
                    vanilla_rate=vanilla_rate,
                    user_rate=saved_user_rate,
                    is_spoiled=saved_spoil,
                    source_entity="Pending Route",
                    is_100_percent=False
                )
                self.drop_configs.append(cfg)

            if hasattr(self, "summary_badge"):
                self.summary_badge.setText(f"{len(self.scanned_sets)} Mod Sets Detected ({len(self.drop_configs)} Items)")

            self._recalculate_distribution()
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", f"Error scanning mods: {e}")

    def _recalculate_distribution(self):
        add_type = AdditionType(self.addition_type_combo.currentData())
        anti_dup = AntiDup(self.anti_dup_combo.currentData())

        # Persist mode choices
        self.config.addition_type = add_type.value
        self.config.anti_dup = anti_dup.value
        self.config.save(self.config_path)

        self.distributor.reset_rotation_state()

        for s, cfg in zip(self.scanned_sets, self.drop_configs):
            target = self.distributor.distribute_set(
                s,
                addition_type=add_type,
                anti_dup=anti_dup,
                global_rate_multiplier_percent=self.global_multiplier_percent
            )
            cfg.source_entity = target.display_name
            cfg.vanilla_rate = target.chance_or_cost

        self.current_page = 1
        self._render_table_page()

    def _render_table_page(self):
        total_items = len(self.drop_configs)
        total_pages = max(1, math.ceil(total_items / self.items_per_page))
        self.current_page = min(max(1, self.current_page), total_pages)
        if total_items == 0:
            self.page_label.setText("No items found. Click 'Scan Input Mods' above.")
        else:
            self.page_label.setText(f"Page {self.current_page} of {total_pages} ({total_items} items total)")

        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)

        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.drop_configs[start_idx:end_idx]

        self.items_table.setRowCount(len(page_items))

        for row_idx, cfg in enumerate(page_items):
            # 0. Item Name
            self.items_table.setItem(row_idx, 0, QTableWidgetItem(cfg.name))

            # 1. Location (Mystery protection)
            is_revealed = self.global_spoiled or cfg.is_spoiled
            loc_text = cfg.source_entity if is_revealed else "🔒 [??? Mystery Location]"
            loc_item = QTableWidgetItem(loc_text)
            if not is_revealed:
                loc_item.setForeground(QColor("#9e9a91"))
            self.items_table.setItem(row_idx, 1, loc_item)

            # 2. Vanilla %
            self.items_table.setItem(row_idx, 2, QTableWidgetItem(f"{cfg.vanilla_rate}%"))

            # 3. User Configured Spinbox
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.1, 100000.0)
            spinbox.setValue(cfg.user_rate)
            spinbox.valueChanged.connect(lambda val, c=cfg: self._on_user_rate_changed(c, val))
            self.items_table.setCellWidget(row_idx, 3, spinbox)

            # 4. Final Rate (with Color Coding: Green > default, Red < default, Grey == default)
            final_rate = self.distributor.calculate_final_rate(cfg.user_rate, self.global_multiplier_percent)
            color_status = self.distributor.get_rate_color_status(final_rate, cfg.vanilla_rate)

            final_item = QTableWidgetItem(f"{final_rate}%")
            if color_status == "green":
                final_item.setForeground(QColor("#48c774"))  # Green
            elif color_status == "red":
                final_item.setForeground(QColor("#ff5252"))  # Red
            else:
                final_item.setForeground(QColor("#9e9a91"))  # Grey

            self.items_table.setItem(row_idx, 4, final_item)

            # 5. Reset Button
            reset_btn = QPushButton("Reset")
            reset_btn.clicked.connect(lambda _, c=cfg, sb=spinbox: self._reset_item_rate(c, sb))
            self.items_table.setCellWidget(row_idx, 5, reset_btn)

            # 6. Eye Toggle Button
            eye_btn = QPushButton("👁 Spoil" if not cfg.is_spoiled else "🔒 Hide")
            eye_btn.clicked.connect(lambda _, c=cfg: self._toggle_item_spoil(c))
            self.items_table.setCellWidget(row_idx, 6, eye_btn)

    def _on_user_rate_changed(self, cfg: ItemDropConfig, val: float):
        cfg.user_rate = val
        self.config.user_drop_rates[cfg.item_key] = val
        self.config.save(self.config_path)
        self._render_table_page()

    def _reset_item_rate(self, cfg: ItemDropConfig, spinbox: QDoubleSpinBox):
        cfg.user_rate = cfg.vanilla_rate
        if cfg.item_key in self.config.user_drop_rates:
            del self.config.user_drop_rates[cfg.item_key]
        self.config.save(self.config_path)
        spinbox.setValue(cfg.vanilla_rate)
        self._render_table_page()

    def _toggle_item_spoil(self, cfg: ItemDropConfig):
        cfg.is_spoiled = not cfg.is_spoiled
        self.config.item_spoiled_states[cfg.item_key] = cfg.is_spoiled
        self.config.save(self.config_path)
        self._render_table_page()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_table_page()

    def _next_page(self):
        total_pages = max(1, math.ceil(len(self.drop_configs) / self.items_per_page))
        if self.current_page < total_pages:
            self.current_page += 1
            self._render_table_page()

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
        reply = QMessageBox.question(
            self, "Confirm Restore", "Restore pristine regulation.bin from the latest backup?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
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

        active_input = self.active_reg_input.text().strip()

        # 0. Backup game assets if game directory is configured
        if self.config.game_directory:
            system_logger.info(
                "Backing up vanilla game assets to backups/ folder...",
                source="Forge"
            )
            self.regulation_manager.backup_game_assets(self.config.game_directory)

        # 1. Resolve source regulation
        source_reg = self.regulation_manager.resolve_source_regulation(
            active_path=active_input,
            game_dir=self.config.game_directory,
            output_dir=self.config.output_directory
        )

        if not source_reg or not source_reg.exists():
            QMessageBox.critical(
                self,
                "Regulation Not Found",
                "Could not find a valid Elden Ring regulation.bin to read from!\n\n"
                "Please configure your Game Directory or browse for an existing regulation.bin."
            )
            return

        # 2. Resolve target regulation (e.g. mod/regulation.bin)
        target_reg = self.regulation_manager.resolve_target_regulation(
            active_path=active_input,
            output_dir=self.config.output_directory,
            game_dir=self.config.game_directory
        )

        try:
            # 3. Pre-write backup if target regulation already exists
            if target_reg.exists():
                self.backup_manager.create_backup(str(target_reg))

            injected_count = 0
            patch_specs = []

            for s, cfg in zip(self.scanned_sets, self.drop_configs):
                # Update configured drop rate
                if s.loot_target:
                    s.loot_target.chance_or_cost = self.distributor.calculate_final_rate(
                        cfg.user_rate, self.global_multiplier_percent
                    )

                # Stage and renumber files into output mod folder
                input_p = Path(self.config.input_directory)
                if not input_p.is_absolute():
                    input_p = self.base_dir / input_p
                staged = self.asset_renumberer.stage_mod_set(str(input_p), s)

                # Build param patch spec
                spec = self.param_builder.build_patch_spec(s)
                patch_specs.append(spec)

                # Record in manifest
                self.manifest_store.record_set(s, staged)
                injected_count += 1

            # 4. Execute RegTool to actually decrypt, patch, and encrypt regulation.bin!
            system_logger.info(
                f"Executing regulation patch from {source_reg} -> {target_reg}...",
                source="Forge"
            )
            patch_result = self.regulation_manager.execute_patch(
                specs=patch_specs,
                source_reg=source_reg,
                target_reg=target_reg,
                game_dir=self.config.game_directory  # ← Pass game_dir for FMG text extraction
            )

            # 5. Deploy parts files (custom models) to same directory as regulation.bin
            output_dir = target_reg.parent  # ✅ Use same directory as target regulation
            
            input_dir = Path(self.config.input_directory)
            if not input_dir.is_absolute():
                input_dir = self.base_dir / input_dir

            parts_deployed = self.regulation_manager.deploy_parts(
                mod_sets=self.scanned_sets,
                input_base_dir=input_dir,
                output_dir=output_dir
            )

            system_logger.info(f"Deployed {parts_deployed} parts files to {output_dir / 'parts'}", source="Forge")

            # Update GUI and config with the new active regulation
            self.active_reg_input.setText(str(target_reg))
            self.config.active_regulation_path = str(target_reg)
            self.config.save(self.config_path)

            # Build detailed success message
            file_size_mb = round(patch_result["target_size_bytes"] / (1024 * 1024), 2)
            
            msg_status = "✅" if (output_dir / "msg" / "engUS" / "item.msgbnd.dcx").exists() else "⚠️"
            parts_status = "✅" if parts_deployed > 0 else "⚠️"
            
            success_msg = (
                f"Successfully forged and injected {injected_count} standalone mod set(s)!\n\n"
                f"✅ Regulation: '{target_reg}' ({file_size_mb} MB)\n"
                f"{msg_status} FMG Text: {output_dir / 'msg' / 'engUS'}\n"
                f"{parts_status} Parts Files: {parts_deployed} deployed to {output_dir / 'parts'}\n\n"
                f"Your vanilla loot tables and gear were preserved 100%.\n"
                f"Ready to launch with Mod Engine 2 or your mod manager!"
            )

            QMessageBox.information(self, "Forge Complete", success_msg)
        except Exception as e:
            system_logger.error(f"Forge execution failed: {e}", source="Forge")
            QMessageBox.critical(self, "Forge Error", f"Forge execution failed: {e}")

    def _uninstall_mods(self):
        reply = QMessageBox.question(
            self, "Confirm Rollback", "Uninstall all staged standalone mods and revert manifest?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for rec in self.manifest_store.get_all_records():
                    self.asset_renumberer.cleanup_files(rec.staged_files)
                self.manifest_store.clear()
                QMessageBox.information(self, "Rollback Complete", "All injected mods have been cleanly uninstalled.")
                self._scan_mods()
            except Exception as e:
                QMessageBox.critical(self, "Rollback Error", f"Uninstall failed: {e}")

    def _toggle_dev_console(self):
        if self.console_drawer.isVisible():
            self.console_drawer.hide()
        else:
            self.console_drawer.show()

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
