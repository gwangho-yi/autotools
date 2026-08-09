import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton,
    QRadioButton, QButtonGroup, QScrollArea, QApplication
)
from PySide6.QtCore import Qt, Signal

from autotools_shared.models import ClickPoint
from autotools_shared.overlay.point_picker import pick_point


def _spin_style() -> str:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
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

        self._ms_spin = QSpinBox()
        self._ms_spin.setRange(0, 10000)
        self._ms_spin.setSingleStep(100)   # 위/아래 버튼 100ms 단위 증감
        self._ms_spin.setValue(self._point.ms)
        self._ms_spin.setSuffix(" ms")
        self._ms_spin.setFixedWidth(90)
        self._ms_spin.setStyleSheet(_spin_style())
        layout.addWidget(self._ms_spin)

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


_BTN_ADD = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
"""


class ClickPointList(QWidget):
    """클릭 포인트 목록 편집 위젯(헤더 + 스크롤 목록 + 포인트 추가 버튼).

    포인트 추가/삭제 시 changed 시그널을 낸다. CaptureRow 등 목록 위/아래에 붙는
    부가 행은 이 위젯이 관리하지 않으며, 번호 오프셋은 set_index_offset로 조정한다.
    """
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[ClickPointRow] = []
        self._index_offset = 0
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 8, 0)
        for text, width in [("#", 26), ("위치", 108), ("딜레이 (ms)", 230), ("종류", 103)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet("color: #444466; font-size: 11px;")
            header.addWidget(lbl)
        header.addStretch()
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setAlignment(Qt.AlignTop)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._list_container)
        scroll.setFixedHeight(150)   # 포인트 목록 영역 고정 높이(약 3행 후 스크롤)
        root.addWidget(scroll)

        self._add_btn = QPushButton("+ 포인트 추가")
        self._add_btn.setStyleSheet(_BTN_ADD)
        self._add_btn.clicked.connect(self._on_add_point)
        root.addWidget(self._add_btn)

    def set_index_offset(self, offset: int) -> None:
        self._index_offset = offset
        self._renumber()

    def points(self) -> list[ClickPoint]:
        return [r.point for r in self._rows]

    def count(self) -> int:
        return len(self._rows)

    def _on_add_point(self) -> None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_point()
        win.show()
        win.raise_()
        win.activateWindow()
        if result is None:
            return
        point = ClickPoint(x=result[0], y=result[1])
        row = ClickPointRow(len(self._rows), point)
        row.delete_requested.connect(self._on_delete_row)
        row.pick_position_requested.connect(self._on_pick_position)
        self._rows.append(row)
        self._list_layout.addWidget(row)
        self._renumber()
        self.changed.emit()

    def _on_pick_position(self, row: ClickPointRow) -> None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_point()
        win.show()
        win.raise_()
        win.activateWindow()
        if result is None:
            return
        row.set_position(result[0], result[1])

    def _on_delete_row(self, row: ClickPointRow) -> None:
        self._rows.remove(row)
        self._list_layout.removeWidget(row)
        row.deleteLater()
        self._renumber()
        self.changed.emit()

    def _renumber(self) -> None:
        for i, r in enumerate(self._rows):
            r.set_index(i + self._index_offset)
