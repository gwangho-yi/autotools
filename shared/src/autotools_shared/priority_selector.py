"""감지점 선택 우선순위 위젯(왼쪽/오른쪽/위/아래/랜덤).

방향 버튼은 누른 순서가 우선순위(1순위, 2순위)가 된다. 같은 축(가로 left/right,
세로 top/bottom)의 반대쪽을 누르면 그 자리를 교체한다. 랜덤은 방향 선택과 상호배타.
priority()는 select_target에 넘길 값을 반환한다: "random" 또는 방향 리스트.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal

_DIRS = [("left", "왼쪽"), ("right", "오른쪽"), ("top", "위"), ("bottom", "아래")]
_BADGE = ["①", "②"]

_BTN_STYLE = """
    QPushButton {
        background-color: #2a2a4e; color: #aaaaaa;
        border: 1px solid #3a3a6e; border-radius: 6px;
        font-size: 12px; padding: 4px 8px;
    }
    QPushButton:checked {
        background-color: #4ecca3; color: #1a1a2e; font-weight: bold;
        border: 1px solid #4ecca3;
    }
    QPushButton:hover { border: 1px solid #4ecca3; }
"""


def _axis(d: str) -> str:
    return "x" if d in ("left", "right") else "y"


class PrioritySelector(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._order: list[str] = ["left", "top"]  # 기본: 좌상단 우선
        self._random = False
        self._btns: dict[str, QPushButton] = {}
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        lbl = QLabel("우선순위:")
        lbl.setStyleSheet("color: #888888; font-size: 12px;")
        row.addWidget(lbl)
        for key, text in _DIRS:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setStyleSheet(_BTN_STYLE)
            b.clicked.connect(lambda _checked=False, k=key: self._on_dir(k))
            self._btns[key] = b
            row.addWidget(b)
        rb = QPushButton("랜덤")
        rb.setCheckable(True)
        rb.setStyleSheet(_BTN_STYLE)
        rb.clicked.connect(self._on_random)
        self._btns["random"] = rb
        row.addWidget(rb)
        row.addStretch()

    def _on_dir(self, key: str) -> None:
        self._random = False
        axis = _axis(key)
        replaced = False
        for i, d in enumerate(self._order):
            if _axis(d) == axis:
                self._order[i] = key   # 같은 축이면 교체(순위 유지)
                replaced = True
                break
        if not replaced:
            self._order.append(key)
            self._order = self._order[:2]  # 축은 최대 2개
        self._refresh()
        self.changed.emit()

    def _on_random(self) -> None:
        self._random = True
        self._order = []
        self._refresh()
        self.changed.emit()

    def _refresh(self) -> None:
        for key, text in _DIRS:
            b = self._btns[key]
            if key in self._order:
                idx = self._order.index(key)
                b.setChecked(True)
                b.setText(f"{text} {_BADGE[idx]}")
            else:
                b.setChecked(False)
                b.setText(text)
        self._btns["random"].setChecked(self._random)

    def priority(self):
        """select_target에 넘길 값. "random" 또는 방향 리스트(1순위부터)."""
        return "random" if self._random else list(self._order)
