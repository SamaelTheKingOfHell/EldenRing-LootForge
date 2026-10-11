"""
Parameter Widget Factory for LootForge Qt GUI.

Automatically constructs and binds UI widgets based on ParamDescriptor types
and purpose groupings per [CS-MODULAR] and [CS-DECOUPLE].
"""

from typing import Dict, Any, Callable, List, Optional, Tuple
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider,
        QCheckBox, QFrame, QFileDialog, QSizePolicy
    )
    from PySide6.QtCore import Qt
except (ImportError, Exception):
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider,
        QCheckBox, QFrame, QFileDialog, QSizePolicy
    )
    from PyQt6.QtCore import Qt

from src.ui.param_schema import ParamDescriptor, ParamType, ParamPurpose


class ParamWidgetFactory:
    """
    Data-driven widget generator for engine parameters.
    
    Why:
        Eliminates manual boilerplate widget wiring. Any new generator parameter
        added to ParamSchema is automatically rendered with correct controls.
    """

    @staticmethod
    def create_control(
        desc: ParamDescriptor,
        initial_value: Any,
        on_change: Callable[[str, Any], None],
        parent: Optional[QWidget] = None
    ) -> Tuple[QWidget, Any]:
        """
        Creates a single typed input control for the given parameter descriptor.
        Returns (container_widget, primary_input_widget).
        """
        if desc.param_type == ParamType.BOOL:
            cb = QCheckBox(desc.label, parent)
            cb.setChecked(bool(initial_value))
            cb.setToolTip(desc.description)
            cb.toggled.connect(lambda checked: on_change(desc.key, checked))
            return cb, cb

        elif desc.param_type == ParamType.ENUM:
            combo = QComboBox(parent)
            combo.setToolTip(desc.description)
            if desc.enum_options:
                for label, val in desc.enum_options:
                    combo.addItem(label, val)
            
            # Select matching item
            for i in range(combo.count()):
                item_data = combo.itemData(i)
                enum_val = getattr(item_data, "value", item_data)
                curr_val = getattr(initial_value, "value", initial_value)
                if item_data == initial_value or enum_val == curr_val:
                    combo.setCurrentIndex(i)
                    break

            combo.currentIndexChanged.connect(lambda idx: on_change(desc.key, combo.itemData(idx)))
            return combo, combo

        elif desc.param_type == ParamType.INT:
            spin = QSpinBox(parent)
            spin.setRange(
                desc.min_value if desc.min_value is not None else 0,
                desc.max_value if desc.max_value is not None else 999999
            )
            spin.setSingleStep(desc.step if desc.step is not None else 1)
            spin.setValue(int(initial_value) if initial_value is not None else (desc.default or 0))
            if desc.unit:
                spin.setSuffix(f" {desc.unit}")
            spin.setToolTip(desc.description)
            spin.valueChanged.connect(lambda val: on_change(desc.key, val))
            return spin, spin

        elif desc.param_type == ParamType.FLOAT:
            spin = QDoubleSpinBox(parent)
            spin.setRange(
                desc.min_value if desc.min_value is not None else 0.0,
                desc.max_value if desc.max_value is not None else 100000.0
            )
            spin.setSingleStep(desc.step if desc.step is not None else 1.0)
            spin.setValue(float(initial_value) if initial_value is not None else (desc.default or 0.0))
            if desc.unit:
                spin.setSuffix(f" {desc.unit}")
            spin.setToolTip(desc.description)
            spin.valueChanged.connect(lambda val: on_change(desc.key, val))
            return spin, spin

        elif desc.param_type in (ParamType.PATH_FILE, ParamType.PATH_DIR):
            row_widget = QWidget(parent)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            line_edit = QLineEdit(row_widget)
            line_edit.setText(str(initial_value or ""))
            line_edit.setToolTip(desc.description)
            line_edit.textChanged.connect(lambda text: on_change(desc.key, text.strip()))
            row_layout.addWidget(line_edit, stretch=1)

            btn_text = "📄 Browse File..." if desc.param_type == ParamType.PATH_FILE else "📁 Browse Folder..."
            browse_btn = QPushButton(btn_text, row_widget)

            def _browse():
                curr = line_edit.text().strip()
                start_dir = curr if curr and Path(curr).exists() else ""
                if desc.param_type == ParamType.PATH_FILE:
                    f_filter = desc.file_filter or "All Files (*)"
                    path, _ = QFileDialog.getOpenFileName(parent, f"Select {desc.label}", start_dir, f_filter)
                else:
                    path = QFileDialog.getExistingDirectory(parent, f"Select {desc.label}", start_dir)
                if path:
                    line_edit.setText(path)

            browse_btn.clicked.connect(_browse)
            row_layout.addWidget(browse_btn)
            return row_widget, line_edit

        else:
            line_edit = QLineEdit(parent)
            line_edit.setText(str(initial_value or ""))
            line_edit.setToolTip(desc.description)
            line_edit.textChanged.connect(lambda text: on_change(desc.key, text.strip()))
            return line_edit, line_edit

    @classmethod
    def build_paths_card(
        cls,
        descriptors: List[ParamDescriptor],
        config: Any,
        on_change: Callable[[str, Any], None],
        on_mod_engine: Callable[[], None],
        on_vanilla: Callable[[], None],
        on_backup: Callable[[], None],
        on_restore: Callable[[], None],
        parent: Optional[QWidget] = None
    ) -> Tuple[QFrame, Dict[str, Any]]:
        """Constructs the Path configuration card with helper preset buttons."""
        card = QFrame(parent)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls: Dict[str, Any] = {}
        for d in descriptors:
            if d.purpose != ParamPurpose.PATHS:
                continue
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{d.label}:"), stretch=0)
            initial_val = getattr(config, d.key, d.default)
            widget_container, input_ctrl = cls.create_control(d, initial_val, on_change, parent=card)
            row.addWidget(widget_container, stretch=1)
            layout.addLayout(row)
            controls[d.key] = input_ctrl

        # Quick preset buttons
        btns_row = QHBoxLayout()
        btns_row.setSpacing(8)
        use_mod_btn = QPushButton("Use Mod Engine (mod/regulation.bin)", card)
        use_mod_btn.clicked.connect(on_mod_engine)
        btns_row.addWidget(use_mod_btn)

        use_vanilla_btn = QPushButton("Use Vanilla Game Regulation", card)
        use_vanilla_btn.clicked.connect(on_vanilla)
        btns_row.addWidget(use_vanilla_btn)

        btns_row.addStretch()

        backup_btn = QPushButton("Create Backup", card)
        backup_btn.clicked.connect(on_backup)
        btns_row.addWidget(backup_btn)
        controls["backup_btn"] = backup_btn

        restore_btn = QPushButton("Restore Latest Backup", card)
        restore_btn.clicked.connect(on_restore)
        btns_row.addWidget(restore_btn)
        controls["restore_btn"] = restore_btn

        layout.addLayout(btns_row)
        return card, controls

    @classmethod
    def build_drop_style_card(
        cls,
        descriptors: List[ParamDescriptor],
        config: Any,
        on_change: Callable[[str, Any], None],
        parent: Optional[QWidget] = None
    ) -> Tuple[QFrame, Dict[str, Any]]:
        """Constructs the Loot & Drop Rules card."""
        card = QFrame(parent)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        card_title = QLabel("⚔️ LOOT & DROP RULES (ENUMS & SCALING)")
        card_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 12px;")
        layout.addWidget(card_title)

        controls: Dict[str, Any] = {}
        row = QHBoxLayout()
        row.setSpacing(12)

        for d in descriptors:
            if d.purpose != ParamPurpose.DROP_STYLE:
                continue

            if d.key == "global_multiplier_percent":
                mult_vbox = QVBoxLayout()
                mult_vbox.setSpacing(4)
                init_mult = int(getattr(config, d.key, 100))
                ratio = round(init_mult / 100.0, 2)
                mult_label = QLabel(f"<b>{d.label}</b>: {init_mult}% ({ratio}x)")
                mult_vbox.addWidget(mult_label)

                slider_row = QHBoxLayout()
                slider = QSlider(Qt.Orientation.Horizontal, card)
                slider.setRange(int(d.min_value or 10), int(d.max_value or 300))
                slider.setValue(init_mult)
                slider_row.addWidget(slider, stretch=1)

                reset_btn = QPushButton("Reset 100%", card)
                reset_btn.clicked.connect(lambda: slider.setValue(100))
                slider_row.addWidget(reset_btn)

                def _slider_changed(val: int):
                    r = round(val / 100.0, 2)
                    mult_label.setText(f"<b>{d.label}</b>: {val}% ({r}x)")
                    on_change(d.key, float(val))

                slider.valueChanged.connect(_slider_changed)
                mult_vbox.addLayout(slider_row)
                row.addLayout(mult_vbox, stretch=1)
                controls[d.key] = slider
                controls["mult_label"] = mult_label
            else:
                vbox = QVBoxLayout()
                vbox.setSpacing(4)
                vbox.addWidget(QLabel(f"<b>{d.label}</b>:"))
                initial_val = getattr(config, d.key, d.default)
                _, ctrl = cls.create_control(d, initial_val, on_change, parent=card)
                vbox.addWidget(ctrl)
                row.addLayout(vbox, stretch=1)
                controls[d.key] = ctrl

        layout.addLayout(row)
        return card, controls

    @classmethod
    def build_diablo_card(
        cls,
        descriptors: List[ParamDescriptor],
        config: Any,
        on_change: Callable[[str, Any], None],
        parent: Optional[QWidget] = None
    ) -> Tuple[QFrame, Dict[str, Any]]:
        """Constructs the Diablo Procedural ARPG Loot card."""
        card = QFrame(parent)
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        card_title = QLabel("⚡ DIABLO PROCEDURAL ARPG RELIC GENERATOR")
        card_title.setStyleSheet("font-weight: bold; color: #ffd475; font-size: 12px;")
        layout.addWidget(card_title)

        controls: Dict[str, Any] = {}
        row = QHBoxLayout()
        row.setSpacing(14)

        for d in descriptors:
            if d.purpose != ParamPurpose.DIABLO_ARPG:
                continue
            vbox = QVBoxLayout()
            vbox.setSpacing(4)
            if d.param_type != ParamType.BOOL:
                vbox.addWidget(QLabel(f"<b>{d.label}</b>:"))
            initial_val = getattr(config, d.key, d.default)
            _, ctrl = cls.create_control(d, initial_val, on_change, parent=card)
            vbox.addWidget(ctrl)
            row.addLayout(vbox, stretch=1 if d.param_type == ParamType.BOOL else 0)
            controls[d.key] = ctrl

        layout.addLayout(row)

        desc_label = QLabel(
            "✦ Rolls random rarity tiers (Common to Mythic), prefix/suffix stat infusions, and authentic "
            "FromSoftware SpEffect passives (HP regen, FP on kill, successive hit ramps) formatted into in-game lore."
        )
        desc_label.setStyleSheet("color: #9e9a91; font-size: 11px; line-height: 1.3;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        return card, controls
