from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QRadioButton, QButtonGroup
from PySide6.QtCore import Qt

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


class CaptureRow(QWidget):
    """First row shown when TCP-connected to auto-capture. Position is auto (cursor-set by capture),
    no delay, click type selectable, not deletable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    @property
    def click_type(self) -> str:
        checked_id = self._type_group.checkedId()
        return _CLICK_TYPES[checked_id][1] if checked_id >= 0 else "left"

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        num_label = QLabel("1")
        num_label.setFixedWidth(18)
        num_label.setStyleSheet("color: #4ecca3; font-size: 12px; font-weight: bold;")
        layout.addWidget(num_label)

        pos_label = QLabel("auto")
        pos_label.setFixedWidth(100)
        pos_label.setAlignment(Qt.AlignCenter)
        pos_label.setStyleSheet("""
            QLabel {
                background-color: #1a3a1a;
                color: #4ecca3;
                border: 1px solid #4ecca3;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px 6px;
            }
        """)
        layout.addWidget(pos_label)

        delay_label = QLabel("딜레이 없음")
        delay_label.setFixedWidth(272)
        delay_label.setAlignment(Qt.AlignCenter)
        delay_label.setStyleSheet("color: #3a3a5e; font-size: 11px;")
        layout.addWidget(delay_label)

        self._type_group = QButtonGroup(self)
        for i, (label, _) in enumerate(_CLICK_TYPES):
            rb = QRadioButton(label)
            rb.setStyleSheet(_RADIO_STYLE)
            self._type_group.addButton(rb, i)
            layout.addWidget(rb)
        self._type_group.button(0).setChecked(True)

        layout.addStretch()

        # Placeholder to align with the delete button column in regular rows
        placeholder = QLabel()
        placeholder.setFixedSize(26, 26)
        layout.addWidget(placeholder)

        self.setStyleSheet("""
            CaptureRow {
                background-color: #1a2a1e;
                border-radius: 6px;
            }
        """)
        self.setFixedHeight(48)
