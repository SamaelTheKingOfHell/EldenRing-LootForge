"""
Interactive Loot Review Modal for LootForge Qt GUI.

Provides a dedicated full-featured dialog for reviewing, filtering,
and customizing item drop rates, mystery mode, and Diablo affixes.
"""

import math
from typing import List, Callable, Optional

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QComboBox, QDoubleSpinBox, QFrame, QSizePolicy, QWidget
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
        QComboBox, QDoubleSpinBox, QFrame, QSizePolicy, QWidget
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor

from src.models import ItemDropConfig
from src.loot_distributor import LootDistributor
from src.ui.theme import DARK_SOULS_QSS


class LootReviewModal(QDialog):
    """
    Dedicated modal dialog for inspecting and fine-tuning loot distributions.
    
    Why:
        Frees up main window vertical space and gives players a focused,
        searchable view of all dropped gear and their exact game locations.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_rate_changed: Optional[Callable[[ItemDropConfig, float], None]] = None,
        on_rate_reset: Optional[Callable[[ItemDropConfig, QDoubleSpinBox], None]] = None,
        on_spoil_toggle: Optional[Callable[[ItemDropConfig], None]] = None,
        on_global_spoil_toggle: Optional[Callable[[], None]] = None,
        on_page_size_changed: Optional[Callable[[int], None]] = None,
        on_custom_art_toggle: Optional[Callable[[ItemDropConfig, bool], None]] = None,
        distributor: Optional[LootDistributor] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("LootForge: Injected Loot Distribution & Drop Rates")
        self.resize(1050, 680)
        self.setMinimumSize(850, 500)
        self.setStyleSheet(DARK_SOULS_QSS)

        self.on_rate_changed = on_rate_changed
        self.on_rate_reset = on_rate_reset
        self.on_spoil_toggle = on_spoil_toggle
        self.on_global_spoil_toggle = on_global_spoil_toggle
        self.on_page_size_changed = on_page_size_changed
        self.on_custom_art_toggle = on_custom_art_toggle
        self.distributor = distributor

        # State
        self.drop_configs: List[ItemDropConfig] = []
        self.filtered_configs: List[ItemDropConfig] = []
        self.global_multiplier_percent: float = 100.0
        self.global_spoiled: bool = True
        self.diablo_enabled: bool = False
        self.current_page: int = 1
        self.items_per_page: int = 8
        self.filter_query: str = ""

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header Bar
        header = QHBoxLayout()
        title = QLabel("⚔️ INJECTED LOOT & DROP RATES MODAL")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffd475; letter-spacing: 1px;")
        header.addWidget(title)

        self.stats_badge = QLabel("0 Items Scanned")
        self.stats_badge.setStyleSheet(
            "background-color: #161924; color: #c5a059; border: 1px solid rgba(197, 160, 89, 0.35); "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        header.addWidget(self.stats_badge)
        header.addStretch()

        self.global_spoil_btn = QPushButton("🔒 Enable Mystery Mode")
        self.global_spoil_btn.clicked.connect(self._handle_global_spoil)
        header.addWidget(self.global_spoil_btn)
        layout.addLayout(header)

        # Search and Page Size Filter Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter items or target drop locations...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_input, stretch=1)

        filter_bar.addWidget(QLabel("Show:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItem("8 items", 8)
        self.page_size_combo.addItem("15 items", 15)
        self.page_size_combo.addItem("25 items", 25)
        self.page_size_combo.addItem("50 items", 50)
        self.page_size_combo.addItem("All items", -1)
        self.page_size_combo.currentIndexChanged.connect(self._handle_page_size_changed)
        filter_bar.addWidget(self.page_size_combo)
        layout.addLayout(filter_bar)

        # Items Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(8)
        self.items_table.setHorizontalHeaderLabels([
            "Mod / Item", "Drop Location", "Vanilla %", "Configured %", "Final %", "Reset", "Reveal", "Moveset / Skill"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.items_table, stretch=1)

        # Pagination Bar
        page_bar = QHBoxLayout()
        self.prev_page_btn = QPushButton("◀ Previous Page")
        self.prev_page_btn.clicked.connect(self._prev_page)
        page_bar.addWidget(self.prev_page_btn)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("color: #ede8df; font-weight: 500;")
        page_bar.addWidget(self.page_label, stretch=1)

        self.next_page_btn = QPushButton("Next Page ▶")
        self.next_page_btn.clicked.connect(self._next_page)
        page_bar.addWidget(self.next_page_btn)
        layout.addLayout(page_bar)

        # Footer Actions
        footer = QHBoxLayout()
        footer_info = QLabel("Drop rates and locations sync live to regulation.bin on Forge.")
        footer_info.setStyleSheet("color: #9e9a91; font-size: 11px;")
        footer.addWidget(footer_info)
        footer.addStretch()

        close_btn = QPushButton("Done / Close")
        close_btn.setProperty("class", "primary")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def set_data(
        self,
        drop_configs: List[ItemDropConfig],
        global_multiplier: float,
        global_spoiled: bool,
        items_per_page: int = 8,
        diablo_enabled: bool = False
    ):
        """Populates modal dataset and updates display controls."""
        self.drop_configs = drop_configs
        self.global_multiplier_percent = global_multiplier
        self.global_spoiled = global_spoiled
        self.diablo_enabled = diablo_enabled
        self.items_per_page = items_per_page

        idx = self.page_size_combo.findData(items_per_page)
        if idx >= 0:
            self.page_size_combo.blockSignals(True)
            self.page_size_combo.setCurrentIndex(idx)
            self.page_size_combo.blockSignals(False)

        self._update_spoil_btn_text()
        self._apply_filter()

    def _update_spoil_btn_text(self):
        if self.global_spoiled:
            self.global_spoil_btn.setText("🔒 Enable Mystery Mode")
        else:
            self.global_spoil_btn.setText("👁 Reveal All Locations")

    def _handle_global_spoil(self):
        self.global_spoiled = not self.global_spoiled
        self._update_spoil_btn_text()
        if self.on_global_spoil_toggle:
            self.on_global_spoil_toggle()
        self.render_table_page()

    def _handle_page_size_changed(self):
        data = self.page_size_combo.currentData()
        if data == -1:
            self.items_per_page = max(1, len(self.filtered_configs)) if self.filtered_configs else 8
        else:
            self.items_per_page = int(data)
        if self.on_page_size_changed:
            self.on_page_size_changed(self.items_per_page)
        self.current_page = 1
        self.render_table_page()

    def _on_search_changed(self, text: str):
        self.filter_query = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        if not self.filter_query:
            self.filtered_configs = list(self.drop_configs)
        else:
            self.filtered_configs = [
                c for c in self.drop_configs
                if self.filter_query in str(c.name).lower()
                or self.filter_query in str(c.source_entity or "").lower()
                or self.filter_query in str(getattr(c, "custom_skill_name", "")).lower()
            ]
        self.current_page = 1
        diablo_tag = " • Diablo ARPG: Active" if self.diablo_enabled else ""
        self.stats_badge.setText(f"{len(self.drop_configs)} Total Items ({len(self.filtered_configs)} Shown){diablo_tag}")
        self.render_table_page()

    def render_table_page(self):
        """Renders the current paginated view into items_table."""
        total = len(self.filtered_configs)
        total_pages = max(1, math.ceil(total / self.items_per_page)) if self.items_per_page > 0 else 1
        self.current_page = min(max(1, self.current_page), total_pages)

        if total == 0:
            self.page_label.setText("No items found matching filter.")
        else:
            self.page_label.setText(f"Page {self.current_page} of {total_pages} ({total} items total)")

        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)

        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.filtered_configs[start_idx:end_idx]

        self.items_table.setRowCount(len(page_items))

        for row_idx, cfg in enumerate(page_items):
            # Item Name (with optional custom skill / moveset badge)
            has_skill = bool(getattr(cfg, "custom_skill_name", ""))
            has_moveset = bool(getattr(cfg, "has_custom_moveset", False))
            if has_skill or has_moveset:
                tags = []
                if has_skill:
                    tags.append(f"✦ Skill: {cfg.custom_skill_name}")
                if has_moveset:
                    tags.append("✦ Moveset")
                name_item = QTableWidgetItem(f"{cfg.name} [{', '.join(tags)}]")
                name_item.setForeground(QColor("#ffd475"))
            else:
                name_item = QTableWidgetItem(cfg.name)
            self.items_table.setItem(row_idx, 0, name_item)

            # Location (Mystery protection)
            is_revealed = self.global_spoiled or cfg.is_spoiled
            loc_text = cfg.source_entity if is_revealed else "🔒 [??? Mystery Location]"
            loc_item = QTableWidgetItem(loc_text)
            if not is_revealed:
                loc_item.setForeground(QColor("#9e9a91"))
            self.items_table.setItem(row_idx, 1, loc_item)

            # Vanilla %
            self.items_table.setItem(row_idx, 2, QTableWidgetItem(f"{cfg.vanilla_rate}%"))

            # User Configured Spinbox
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.1, 100000.0)
            spinbox.setValue(cfg.user_rate)
            spinbox.valueChanged.connect(lambda val, c=cfg: self._on_user_rate(c, val))
            self.items_table.setCellWidget(row_idx, 3, spinbox)

            # Final Rate
            final_rate = cfg.user_rate
            color_status = "grey"
            if self.distributor:
                final_rate = self.distributor.calculate_final_rate(cfg.user_rate, self.global_multiplier_percent)
                color_status = self.distributor.get_rate_color_status(final_rate, cfg.vanilla_rate)

            final_item = QTableWidgetItem(f"{final_rate}%")
            if color_status == "green":
                final_item.setForeground(QColor("#48c774"))
            elif color_status == "red":
                final_item.setForeground(QColor("#ff5252"))
            else:
                final_item.setForeground(QColor("#9e9a91"))
            self.items_table.setItem(row_idx, 4, final_item)

            # Reset Button
            reset_btn = QPushButton("Reset")
            reset_btn.clicked.connect(lambda _, c=cfg, sb=spinbox: self._on_reset(c, sb))
            self.items_table.setCellWidget(row_idx, 5, reset_btn)

            # Reveal / Hide Toggle
            eye_btn = QPushButton("👁 Spoil" if not cfg.is_spoiled else "🔒 Hide")
            eye_btn.clicked.connect(lambda _, c=cfg: self._on_spoil(c))
            self.items_table.setCellWidget(row_idx, 6, eye_btn)

            # Custom Moveset / Skill Action Toggle
            if has_skill or has_moveset:
                art_btn = QPushButton()
                if getattr(cfg, "import_custom_art", True):
                    if has_skill:
                        label = f"✦ Active: {cfg.custom_skill_name}"
                    elif has_moveset:
                        label = "✦ Active: Custom Moveset"
                    else:
                        label = "✦ Active"
                    art_btn.setText(label)
                    art_btn.setStyleSheet("color: #ffd475; border: 1px solid rgba(197, 160, 89, 0.6); background-color: #1a1e2b; font-size: 11px; padding: 2px 6px;")
                else:
                    art_btn.setText("Default (Vanilla/ARPG)")
                    art_btn.setStyleSheet("color: #9e9a91; border: 1px solid rgba(158, 154, 145, 0.3); background-color: #12141a; font-size: 11px; padding: 2px 6px;")
                art_btn.clicked.connect(lambda _, c=cfg: self._on_toggle_custom_art(c))
                self.items_table.setCellWidget(row_idx, 7, art_btn)
            else:
                dash_item = QTableWidgetItem("-")
                dash_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                dash_item.setForeground(QColor("#666666"))
                self.items_table.setItem(row_idx, 7, dash_item)

    def _on_toggle_custom_art(self, cfg: ItemDropConfig):
        cfg.import_custom_art = not getattr(cfg, "import_custom_art", True)
        if self.on_custom_art_toggle:
            self.on_custom_art_toggle(cfg, cfg.import_custom_art)
        self.render_table_page()

    def _on_user_rate(self, cfg: ItemDropConfig, val: float):
        cfg.user_rate = val
        if self.on_rate_changed:
            self.on_rate_changed(cfg, val)
        self.render_table_page()

    def _on_reset(self, cfg: ItemDropConfig, spinbox: QDoubleSpinBox):
        if self.on_rate_reset:
            self.on_rate_reset(cfg, spinbox)
        else:
            cfg.user_rate = cfg.vanilla_rate
            spinbox.setValue(cfg.vanilla_rate)
        self.render_table_page()

    def _on_spoil(self, cfg: ItemDropConfig):
        if self.on_spoil_toggle:
            self.on_spoil_toggle(cfg)
        else:
            cfg.is_spoiled = not cfg.is_spoiled
        self.render_table_page()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.render_table_page()

    def _next_page(self):
        total_pages = max(1, math.ceil(len(self.filtered_configs) / self.items_per_page))
        if self.current_page < total_pages:
            self.current_page += 1
            self.render_table_page()
