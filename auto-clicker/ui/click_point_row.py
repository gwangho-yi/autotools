import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSpinBox, QPushButton, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal

from core.models import ClickPoint


def _spin_style() -> str:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    up = (base / "assets" / "arrow-up.png").as_posix()
    dn = (base / "assets" / "arrow-down.png").as_posix()
    return f"""
    QSpinBox {{
        background-color: #2a2a4e; color: white;
        border: 1px solid #3a3a5e; border-radius: 4px; padding: 1px 2px;
    }}
    QSpinBox::up-button {{
        width: 16px; subcontrol-origin: border; subcontrol-position: top right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::down-button {{
        width: 16px; subcontrol-origin: border; subcontrol-position: bottom right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background-color: #4a4a8e; }}
    QSpinBox::up-arrow {{ image: url("{up}"); width: 9px; height: 6px; }}
    QSpinBox::down-arrow {{ image: url("{dn}"); width: 9px; height: 6px; }}
    """

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


_RADIO_STYLE = """
    QRadioButton {
        color: #888888;
        font-size: 11px;
        spacing: 3px;
    }
    QRadioButton::indicator {
        width: 12px;
        height: 12px;
    }
    QRadioButton::indicator:unchecked {
        border: 1px solid #3a3a5e;
        border-radius: 6px;
        background-color: #2a2a4e;
    }
    QRadioButton::indicator:checked {
        border: 1px solid #4ecca3;
        border-radius: 6px;
        background-color: #4ecca3;
    }
    QRadioButton:checked { color: #4ecca3; }
"""

_CLICK_TYPES = [("좌", "left"), ("우", "right"), ("더블", "double")]


class ClickPointRow(QWidget):
    delete_requested = Signal(object)
    pick_position_requested = Signal(object)

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
        checked_id = self._type_group.checkedId()
        self._point.click_type = _CLICK_TYPES[checked_id][1] if checked_id >= 0 else "left"
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
        self._pos_btn.clicked.connect(lambda: self.pick_position_requested.emit(self))
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
            spin.setStyleSheet(_spin_style())
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666666; font-size: 11px;")
            lbl.setFixedWidth(16)
            layout.addWidget(spin)
            layout.addWidget(lbl)
            setattr(self, attr, spin)

        self._type_group = QButtonGroup(self)
        default_idx = next(
            (i for i, (_, v) in enumerate(_CLICK_TYPES) if v == self._point.click_type), 0
        )
        for i, (label, _) in enumerate(_CLICK_TYPES):
            rb = QRadioButton(label)
            rb.setStyleSheet(_RADIO_STYLE)
            self._type_group.addButton(rb, i)
            layout.addWidget(rb)
        self._type_group.button(default_idx).setChecked(True)

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
