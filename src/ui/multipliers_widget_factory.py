"""
Multipliers Widget Factory for LootForge Qt GUI.
Constructs synchronized slider controls for Master, Stats/Boosts, and Item Price multipliers.
Complies with [CS-MODULAR] and [CS-GRANULARITY] (<= 300 lines).
"""

from typing import Dict, Any, Callable, Optional, Tuple

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QFrame
    )
    from PySide6.QtCore import Qt
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QFrame
    )
    from PyQt6.QtCore import Qt


class MultipliersWidgetFactory:
    """
    Constructs the item power and price multiplier cards and sliders.
    """

    @classmethod
    def build_multipliers_card(
        cls,
        config: Any,
        on_change: Callable[[str, Any], None],
        parent: Optional[QWidget] = None
    ) -> Tuple[QFrame, Dict[str, Any]]:
        """Constructs synchronized Master, Stats, and Price multiplier card."""
        card = QFrame(parent)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        card_title = QLabel("⚖️ ITEM POWER & PRICE MULTIPLIERS (STATS & ECONOMY)")
        card_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 12px;")
        layout.addWidget(card_title)

        desc_label = QLabel(
            "Adjust the Master bar to scale stats and prices simultaneously, or fine-tune Stats & Boosts and Item Price independently."
        )
        desc_label.setStyleSheet("color: #9e9a91; font-size: 11px;")
        layout.addWidget(desc_label)

        controls: Dict[str, Any] = {}
        sliders_row = QHBoxLayout()
        sliders_row.setSpacing(14)

        # 1. Master Multiplier
        init_master = int(round(getattr(config, "master_multiplier", 1.0) * 100))
        master_box = QVBoxLayout()
        master_box.setSpacing(3)
        master_label = QLabel(f"<b>⭐ Master (Both)</b>: {init_master}% ({round(init_master / 100.0, 2)}x)")
        master_label.setStyleSheet("color: #ffd475;")
        master_box.addWidget(master_label)
        master_h = QHBoxLayout()
        master_slider = QSlider(Qt.Orientation.Horizontal, card)
        master_slider.setRange(10, 500)
        master_slider.setValue(init_master)
        master_h.addWidget(master_slider, stretch=1)
        master_reset = QPushButton("Reset 100%", card)
        master_h.addWidget(master_reset)
        master_box.addLayout(master_h)
        sliders_row.addLayout(master_box, stretch=1)

        # 2. Stats & Boosts Multiplier
        init_stats = int(round(getattr(config, "stats_multiplier", 1.0) * 100))
        stats_box = QVBoxLayout()
        stats_box.setSpacing(3)
        stats_label = QLabel(f"<b>⚔️ Stats & Boosts</b>: {init_stats}% ({round(init_stats / 100.0, 2)}x)")
        stats_box.addWidget(stats_label)
        stats_h = QHBoxLayout()
        stats_slider = QSlider(Qt.Orientation.Horizontal, card)
        stats_slider.setRange(10, 500)
        stats_slider.setValue(init_stats)
        stats_h.addWidget(stats_slider, stretch=1)
        stats_reset = QPushButton("Reset 100%", card)
        stats_h.addWidget(stats_reset)
        stats_box.addLayout(stats_h)
        sliders_row.addLayout(stats_box, stretch=1)

        # 3. Item Price Multiplier
        init_price = int(round(getattr(config, "price_multiplier", 1.0) * 100))
        price_box = QVBoxLayout()
        price_box.setSpacing(3)
        price_label = QLabel(f"<b>💰 Item Price</b>: {init_price}% ({round(init_price / 100.0, 2)}x)")
        price_box.addWidget(price_label)
        price_h = QHBoxLayout()
        price_slider = QSlider(Qt.Orientation.Horizontal, card)
        price_slider.setRange(10, 500)
        price_slider.setValue(init_price)
        price_h.addWidget(price_slider, stretch=1)
        price_reset = QPushButton("Reset 100%", card)
        price_h.addWidget(price_reset)
        price_box.addLayout(price_h)
        sliders_row.addLayout(price_box, stretch=1)

        layout.addLayout(sliders_row)

        is_syncing = False

        def _update_master_label(pct: int):
            master_label.setText(f"<b>⭐ Master (Both)</b>: {pct}% ({round(pct / 100.0, 2)}x)")

        def _update_stats_label(pct: int):
            stats_label.setText(f"<b>⚔️ Stats & Boosts</b>: {pct}% ({round(pct / 100.0, 2)}x)")

        def _update_price_label(pct: int):
            price_label.setText(f"<b>💰 Item Price</b>: {pct}% ({round(pct / 100.0, 2)}x)")

        def _on_master_changed(val: int):
            nonlocal is_syncing
            if is_syncing:
                return
            is_syncing = True
            try:
                _update_master_label(val)
                stats_slider.setValue(val)
                price_slider.setValue(val)
                _update_stats_label(val)
                _update_price_label(val)
                mult = round(val / 100.0, 2)
                on_change("master_multiplier", mult)
                on_change("stats_multiplier", mult)
                on_change("price_multiplier", mult)
            finally:
                is_syncing = False

        def _on_stats_changed(val: int):
            _update_stats_label(val)
            mult = round(val / 100.0, 2)
            on_change("stats_multiplier", mult)

        def _on_price_changed(val: int):
            _update_price_label(val)
            mult = round(val / 100.0, 2)
            on_change("price_multiplier", mult)

        master_slider.valueChanged.connect(_on_master_changed)
        stats_slider.valueChanged.connect(_on_stats_changed)
        price_slider.valueChanged.connect(_on_price_changed)

        master_reset.clicked.connect(lambda: master_slider.setValue(100))
        stats_reset.clicked.connect(lambda: stats_slider.setValue(100))
        price_reset.clicked.connect(lambda: price_slider.setValue(100))

        controls["master_multiplier"] = master_slider
        controls["stats_multiplier"] = stats_slider
        controls["price_multiplier"] = price_slider
        controls["master_label"] = master_label
        controls["stats_label"] = stats_label
        controls["price_label"] = price_label
        controls["master_reset"] = master_reset
        controls["stats_reset"] = stats_reset
        controls["price_reset"] = price_reset

        return card, controls
