from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton
)
from PySide6.QtCore import Signal

from core.models import ClickPoint

_BTN_STYLE = """
    QPushButton {{
        background-color: #2a2a4e;
        color: {color};
        border: 1px solid {border};
        border-radius: 4px;
        font-size: 11px;
        padding: 2px 6px;
    }}
    QPushButton:hover {{ background-color: #3a3a5e; }}
"""

_SPIN_STYLE = """
    QSpinBox {
        background-color: #2a2a4e;
        color: white;
        border: 1px solid #3a3a5e;
        border-radius: 4px;
        padding: 1px 2px;
    }
    QSpinBox::up-button, QSpinBox::down-button { width: 14px; }
"""

_COMBO_STYLE = """
    QComboBox {
        background-color: #2a2a4e;
        color: white;
        border: 1px solid #3a3a5e;
        border-radius: 4px;
        padding: 1px 4px;
    }
    QComboBox QAbstractItemView {
        background-color: #2a2a4e;
        color: white;
        selection-background-color: #4ecca3;
        selection-color: #1a1a2e;
    }
"""

_CLICK_TYPES = [("왼쪽 클릭", "left"), ("오른쪽 클릭", "right"), ("더블 클릭", "double")]


class ClickPointRow(QWidget):
    delete_requested = Signal(object)  # emits self

    def __init__(self, index: int, point: ClickPoint, parent=None):
        super().__init__(parent)
        self._point = point
        self._build_ui(index)

    @property
    def point(self) -> ClickPoint:
        self._point.hours = self._h_spin.value()
        self._point.minutes = self._m_spin.value()
        self._point.seconds = self._s_spin.value()
        self._point.ms = self._ms_spin.value()
        self._point.click_type = _CLICK_TYPES[self._type_combo.currentIndex()][1]
        return self._point

    def set_index(self, index: int) -> None:
        self._num_label.setText(str(index + 1))

    def set_position(self, x: int, y: int) -> None:
        self._point.x = x
        self._point.y = y
        self._pos_btn.setText(f"({x}, {y})")

    def _build_ui(self, index: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._num_label = QLabel(str(index + 1))
        self._num_label.setFixedWidth(18)
        self._num_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._num_label)

        self._pos_btn = QPushButton(f"({self._point.x}, {self._point.y})")
        self._pos_btn.setFixedWidth(100)
        self._pos_btn.setStyleSheet(_BTN_STYLE.format(color="#4ecca3", border="#4ecca3"))
        layout.addWidget(self._pos_btn)

        for attr, label_text, max_val, init_val in [
            ("_h_spin",  "h",  23,  self._point.hours),
            ("_m_spin",  "m",  59,  self._point.minutes),
            ("_s_spin",  "s",  59,  self._point.seconds),
            ("_ms_spin", "ms", 999, self._point.ms),
        ]:
            spin = QSpinBox()
            spin.setRange(0, max_val)
            spin.setValue(init_val)
            spin.setFixedWidth(52)
            spin.setStyleSheet(_SPIN_STYLE)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666666; font-size: 11px;")
            lbl.setFixedWidth(16)
            layout.addWidget(spin)
            layout.addWidget(lbl)
            setattr(self, attr, spin)

        self._type_combo = QComboBox()
        for label, _ in _CLICK_TYPES:
            self._type_combo.addItem(label)
        default_idx = next(
            (i for i, (_, v) in enumerate(_CLICK_TYPES) if v == self._point.click_type), 0
        )
        self._type_combo.setCurrentIndex(default_idx)
        self._type_combo.setFixedWidth(95)
        self._type_combo.setStyleSheet(_COMBO_STYLE)
        layout.addWidget(self._type_combo)

        layout.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #666666; border: none; font-size: 14px; }
            QPushButton:hover { color: #e05555; }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(del_btn)

        self.setStyleSheet("""
            ClickPointRow {
                background-color: #1e1e3a;
                border-radius: 6px;
            }
        """)
        self.setFixedHeight(48)
