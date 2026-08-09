from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QApplication
)
from PySide6.QtCore import Qt, Signal

from autotools_shared.overlay.point_picker import pick_point

_BTN_POS = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px solid #4ecca3; border-radius: 4px;
        font-size: 11px; padding: 2px 6px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
    QPushButton:disabled { color: #4a6a5e; border-color: #2a4a3e; }
"""

_BTN_ADD = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
    QPushButton:disabled { color: #4a6a5e; border-color: #2a4a3e; }
"""


class ContinuousPointRow(QWidget):
    """연속 클릭 지점 한 줄: [번호] [(x, y) 위치 버튼] ... [✕]

    시퀀스용 ClickPointRow와 달리 지점별 딜레이/클릭 종류 컬럼이 없다.
    딜레이는 전역 min/max 스핀박스로, 클릭 종류는 좌클릭으로 고정되기 때문.
    """
    delete_requested = Signal(object)
    pick_position_requested = Signal(object)

    def __init__(self, index: int, x: int, y: int, parent=None):
        super().__init__(parent)
        self._x = x
        self._y = y
        self._build_ui(index)

    @property
    def point(self) -> tuple[int, int]:
        return (self._x, self._y)

    def set_index(self, index: int) -> None:
        self._num_label.setText(str(index + 1))

    def set_position(self, x: int, y: int) -> None:
        self._x = x
        self._y = y
        self._pos_btn.setText(f"({x}, {y})")

    def set_enabled_editing(self, enabled: bool) -> None:
        self._pos_btn.setEnabled(enabled)
        self._del_btn.setEnabled(enabled)

    def _build_ui(self, index: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._num_label = QLabel(str(index + 1))
        self._num_label.setFixedWidth(18)
        self._num_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._num_label)

        self._pos_btn = QPushButton(f"({self._x}, {self._y})")
        self._pos_btn.setFixedWidth(100)
        self._pos_btn.setStyleSheet(_BTN_POS)
        self._pos_btn.clicked.connect(lambda: self.pick_position_requested.emit(self))
        layout.addWidget(self._pos_btn)

        layout.addStretch()

        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(26, 26)
        self._del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #666666; border: none; font-size: 14px; }
            QPushButton:hover { color: #e05555; }
            QPushButton:disabled { color: #3a3a5e; }
        """)
        self._del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(self._del_btn)

        self.setStyleSheet("""
            ContinuousPointRow {
                background-color: #1e1e3a;
                border-radius: 6px;
            }
        """)
        self.setFixedHeight(36)


class ContinuousPointList(QWidget):
    """연속 클릭 지점 목록 편집 위젯(스크롤 목록 + 지점 추가 버튼).

    지점 추가/삭제 시 changed 시그널을 낸다.
    """
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[ContinuousPointRow] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

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
        scroll.setFixedHeight(200)   # 고정 높이 — 약 5행(36*5 + spacing 4*4 = 196) 후 스크롤
        root.addWidget(scroll)

        self._add_btn = QPushButton("+ 연속 클릭 지점 추가")
        self._add_btn.setStyleSheet(_BTN_ADD)
        self._add_btn.clicked.connect(self._on_add_point)
        root.addWidget(self._add_btn)

    def points(self) -> list[tuple[int, int]]:
        return [r.point for r in self._rows]

    def count(self) -> int:
        return len(self._rows)

    def set_enabled_editing(self, enabled: bool) -> None:
        self._add_btn.setEnabled(enabled)
        for row in self._rows:
            row.set_enabled_editing(enabled)

    def _pick(self) -> tuple[int, int] | None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_point()
        win.show()
        win.raise_()
        win.activateWindow()
        return result

    def _on_add_point(self) -> None:
        result = self._pick()
        if result is None:
            return
        row = ContinuousPointRow(len(self._rows), result[0], result[1])
        row.delete_requested.connect(self._on_delete_row)
        row.pick_position_requested.connect(self._on_pick_position)
        self._rows.append(row)
        self._list_layout.addWidget(row)
        self._renumber()
        self.changed.emit()

    def _on_pick_position(self, row: ContinuousPointRow) -> None:
        result = self._pick()
        if result is None:
            return
        row.set_position(result[0], result[1])

    def _on_delete_row(self, row: ContinuousPointRow) -> None:
        self._rows.remove(row)
        self._list_layout.removeWidget(row)
        row.deleteLater()
        self._renumber()
        self.changed.emit()

    def _renumber(self) -> None:
        for i, r in enumerate(self._rows):
            r.set_index(i)
