from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget, QAbstractSpinBox, QApplication
)
from PySide6.QtCore import Qt, Signal

from autotools_shared.overlay.color_picker import pick_pixel_color
from autotools_shared.overlay.region_select import select_regions
from autotools_shared.priority_selector import PrioritySelector

_BTN_GREEN = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 15px; font-weight: bold;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_RED = """
    QPushButton {
        background-color: #e05555; color: white;
        border: none; border-radius: 8px;
        font-size: 15px; font-weight: bold;
    }
    QPushButton:hover { background-color: #c04444; }
"""

_BTN_OUTLINE = """
    QPushButton {
        background-color: transparent; color: #4ecca3;
        border: 1px solid #4ecca3; border-radius: 8px;
        font-size: 13px; padding: 6px;
    }
    QPushButton:hover { background-color: rgba(78,204,163,0.1); }
"""

_SPIN_STYLE = """
    QSpinBox {
        background-color: #2a2a4e; color: #cccccc;
        border: 1px solid #3a3a6e; border-radius: 4px;
        font-size: 13px; padding: 2px 4px;
    }
"""


class ColorCaptureTab(QWidget):
    start_requested = Signal(list, tuple, int)
    stop_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_rgb: tuple[int, int, int] | None = None
        self._regions: list[dict] | None = None
        self._build_ui()

    @property
    def target_rgb(self) -> tuple[int, int, int] | None:
        return self._target_rgb

    @property
    def regions(self) -> list[dict] | None:
        return self._regions

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 6)
        layout.setSpacing(10)

        # 색 샘플 행 — RGB 입력이 왼쪽, 색 지정 버튼/스와치가 오른쪽
        color_row = QHBoxLayout()
        color_row.setSpacing(8)

        self._rgb_spins: list[QSpinBox] = []
        for label_text in ("R", "G", "B"):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            color_row.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setStyleSheet(_SPIN_STYLE)
            spin.setFixedWidth(70)
            spin.valueChanged.connect(self._on_rgb_spin_changed)
            color_row.addWidget(spin)
            self._rgb_spins.append(spin)

        color_row.addStretch()

        self._pick_color_btn = QPushButton("색 지정")
        self._pick_color_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_color_btn.setFixedSize(78, 32)
        self._pick_color_btn.clicked.connect(self._on_pick_color)
        color_row.addWidget(self._pick_color_btn)

        self._swatch = QLabel()
        self._swatch.setFixedSize(34, 28)
        self._swatch.setStyleSheet("background-color: #2a2a4e; border-radius: 4px;")
        color_row.addWidget(self._swatch)

        layout.addLayout(color_row)

        # 허용오차 행
        tol_row = QHBoxLayout()
        tol_lbl = QLabel("허용오차:")
        tol_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        tol_row.addWidget(tol_lbl)
        self._tolerance = QSpinBox()
        self._tolerance.setRange(0, 100)
        self._tolerance.setValue(10)
        self._tolerance.setStyleSheet(_SPIN_STYLE)
        tol_row.addWidget(self._tolerance)
        tol_row.addStretch()
        layout.addLayout(tol_row)

        self.priority_selector = PrioritySelector()
        layout.addWidget(self.priority_selector)

        layout.addStretch()

        # 시작/일시정지/정지 스택 (launcher.py의 _build_capture_page와 동일한 패턴)
        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)

        # Page 0: idle
        self._start_btn = QPushButton("시작")
        self._start_btn.setFixedHeight(44)
        self._start_btn.setStyleSheet(_BTN_GREEN)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._btn_stack.addWidget(self._start_btn)

        # Page 1: monitoring
        self._pause_btn = QPushButton("일시정지 (Ctrl+F6)")
        self._pause_btn.setFixedHeight(44)
        self._pause_btn.setStyleSheet(_BTN_OUTLINE)
        self._pause_btn.clicked.connect(lambda: self.pause_requested.emit())
        self._btn_stack.addWidget(self._pause_btn)

        # Page 2: paused
        p2 = QWidget()
        p2_l = QHBoxLayout(p2)
        p2_l.setContentsMargins(0, 0, 0, 0)
        p2_l.setSpacing(8)
        self._resume_btn = QPushButton("재시작 (Ctrl+F6)")
        self._resume_btn.setFixedHeight(44)
        self._resume_btn.setStyleSheet(_BTN_GREEN)
        self._resume_btn.clicked.connect(lambda: self.resume_requested.emit())
        p2_l.addWidget(self._resume_btn)
        self._stop_btn = QPushButton("중지")
        self._stop_btn.setFixedHeight(44)
        self._stop_btn.setStyleSheet(_BTN_RED)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        p2_l.addWidget(self._stop_btn)
        self._btn_stack.addWidget(p2)

        layout.addWidget(self._btn_stack)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _refresh_start_enabled(self) -> None:
        self._start_btn.setEnabled(self._target_rgb is not None)

    def _on_pick_color(self) -> None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_pixel_color()
        win.show()
        win.raise_()
        win.activateWindow()
        if result is None:
            return
        _x, _y, rgb = result
        self._set_target_rgb(rgb, sync_spins=True)

    def _set_target_rgb(self, rgb: tuple[int, int, int], sync_spins: bool) -> None:
        self._target_rgb = rgb
        r, g, b = rgb
        self._swatch.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border-radius: 4px;"
        )
        if sync_spins:
            for spin, value in zip(self._rgb_spins, rgb):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        self._refresh_start_enabled()

    def _on_rgb_spin_changed(self, _value: int) -> None:
        rgb = tuple(spin.value() for spin in self._rgb_spins)
        self._set_target_rgb(rgb, sync_spins=False)

    def _on_start(self) -> None:
        if self._target_rgb is None:
            return
        self._start_btn.setEnabled(False)
        self._status_label.setText("영역을 선택하세요...")
        regions = select_regions()
        if not regions:
            self._status_label.setText("")
            self._refresh_start_enabled()
            return
        self._regions = regions
        self.start_requested.emit(self._regions, self._target_rgb, self._tolerance.value())

    def set_monitoring(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._pick_color_btn.setEnabled(not active)
        self._tolerance.setEnabled(not active)
        self.priority_selector.setEnabled(not active)
        if not active:
            self._refresh_start_enabled()

    def set_paused(self) -> None:
        self._btn_stack.setCurrentIndex(2)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def priority(self):
        return self.priority_selector.priority()
