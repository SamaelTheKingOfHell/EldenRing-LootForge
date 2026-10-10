"""
Dark Souls / Elden Ring themed QSS stylesheet for LootForge Qt Application.
Adheres to [CS-MODULAR] by encapsulating styling into a dedicated module.
"""

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
