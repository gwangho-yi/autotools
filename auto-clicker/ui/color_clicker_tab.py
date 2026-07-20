from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget, QApplication
)
from PySide6.QtCore import Qt, Signal

from ui.point_picker import pick_point
from ui.click_point_row import _spin_style  # 기존 스핀박스 스타일 재사용

_BTN_PRIMARY = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 14px; font-weight: bold; padding: 8px 20px;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_DANGER = """
    QPushButton {
        background-color: transparent; color: #e05555;
        border: 1px solid #e05555; border-radius: 8px;
        font-size: 14px; font-weight: bold; padding: 8px 20px;
    }
    QPushButton:hover { background-color: rgba(224,85,85,0.1); }
"""

_BTN_OUTLINE = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
"""


class ColorClickerTab(QWidget):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._point: tuple[int, int] | None = None
        self._build_ui()

    @property
    def point(self) -> tuple[int, int] | None:
        return self._point

    @property
    def min_ms(self) -> int:
        return self._min_spin.value()

    @property
    def max_ms(self) -> int:
        return self._max_spin.value()

    @property
    def click_type(self) -> str:
        return "left"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        desc = QLabel("컬러 감지 전까지 이 지점을 연속 클릭합니다")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)

        self._pick_btn = QPushButton("연속 클릭 지점 지정")
        self._pick_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_btn.clicked.connect(self._on_pick_point)
        layout.addWidget(self._pick_btn)

        # min/max ms 행
        ms_row = QHBoxLayout()
        min_lbl = QLabel("최소:")
        min_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        ms_row.addWidget(min_lbl)
        self._min_spin = QSpinBox()
        self._min_spin.setRange(1, 10000)
        self._min_spin.setValue(80)
        self._min_spin.setSuffix(" ms")
        self._min_spin.setFixedWidth(90)
        self._min_spin.setStyleSheet(_spin_style())
        ms_row.addWidget(self._min_spin)
        max_lbl = QLabel("최대:")
        max_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        ms_row.addWidget(max_lbl)
        self._max_spin = QSpinBox()
        self._max_spin.setRange(1, 10000)
        self._max_spin.setValue(200)
        self._max_spin.setSuffix(" ms")
        self._max_spin.setFixedWidth(90)
        self._max_spin.setStyleSheet(_spin_style())
        ms_row.addWidget(self._max_spin)
        self._ms_error_label = QLabel("")
        self._ms_error_label.setStyleSheet("color: #e05555; font-size: 11px;")
        ms_row.addWidget(self._ms_error_label)
        ms_row.addStretch()
        layout.addLayout(ms_row)

        self._min_spin.valueChanged.connect(self._clear_ms_error)
        self._max_spin.valueChanged.connect(self._clear_ms_error)

        layout.addStretch()

        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)
        self._start_btn = QPushButton("▶ 시작 (Ctrl+F7)")
        self._start_btn.setStyleSheet(_BTN_PRIMARY)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._btn_stack.addWidget(self._start_btn)
        self._stop_btn = QPushButton("■ 중지 (Ctrl+F7)")
        self._stop_btn.setStyleSheet(_BTN_DANGER)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        self._btn_stack.addWidget(self._stop_btn)
        layout.addWidget(self._btn_stack)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _clear_ms_error(self, _value: int) -> None:
        self._ms_error_label.setText("")

    def _on_start_clicked(self) -> None:
        if self._min_spin.value() > self._max_spin.value():
            self._ms_error_label.setText("최소값은 최대값보다 클 수 없습니다")
            return
        self._ms_error_label.setText("")
        self.start_requested.emit()

    def _on_pick_point(self) -> None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_point()
        win.show()
        win.raise_()
        win.activateWindow()
        if result is None:
            return
        x, y = result
        self._point = (x, y)
        self._pick_btn.setText(f"연속 클릭 지점: ({x}, {y})")
        self._start_btn.setEnabled(True)

    def set_running(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._pick_btn.setEnabled(not active)
        self._min_spin.setEnabled(not active)
        self._max_spin.setEnabled(not active)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
