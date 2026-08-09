from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget
)
from PySide6.QtCore import Signal

from autotools_shared.clickpoint_list import _spin_style  # 기존 스핀박스 스타일 재사용
from autotools_shared.continuous_point_list import ContinuousPointList

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

# 루프 OFF: 테두리만, ON: 채움 — 한눈에 상태가 구분되게
_BTN_LOOP_OFF = """
    QPushButton {
        background-color: transparent; color: #888888;
        border: 1px solid #4a4a6e; border-radius: 8px;
        font-size: 13px; padding: 8px 20px;
    }
    QPushButton:hover { background-color: #2a2a4e; }
    QPushButton:disabled { color: #555555; border-color: #33334e; }
"""

_BTN_LOOP_ON = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 13px; font-weight: bold; padding: 8px 20px;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_LOOP_TEXT_OFF = "🔁 루프 꺼짐 (첫 지점만 클릭)"
_LOOP_TEXT_ON = "🔁 루프 켜짐 (전체 순환)"


class ColorClickerTab(QWidget):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    @property
    def points(self) -> list[tuple[int, int]]:
        return self._point_list.points()

    @property
    def loop(self) -> bool:
        return self._loop_btn.isChecked()

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

        desc = QLabel("컬러 감지 전까지 아래 지점들을 연속 클릭합니다")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)

        self._point_list = ContinuousPointList()
        self._point_list.changed.connect(self._on_points_changed)
        layout.addWidget(self._point_list)

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

        self._loop_btn = QPushButton(_LOOP_TEXT_OFF)
        self._loop_btn.setCheckable(True)
        self._loop_btn.setChecked(False)
        self._loop_btn.setStyleSheet(_BTN_LOOP_OFF)
        self._loop_btn.toggled.connect(self._on_loop_toggled)
        layout.addWidget(self._loop_btn)

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

    def _on_points_changed(self) -> None:
        self._start_btn.setEnabled(self._point_list.count() > 0)

    def _on_loop_toggled(self, checked: bool) -> None:
        self._loop_btn.setText(_LOOP_TEXT_ON if checked else _LOOP_TEXT_OFF)
        self._loop_btn.setStyleSheet(_BTN_LOOP_ON if checked else _BTN_LOOP_OFF)

    def set_running(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._point_list.set_enabled_editing(not active)
        self._loop_btn.setEnabled(not active)
        self._min_spin.setEnabled(not active)
        self._max_spin.setEnabled(not active)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
