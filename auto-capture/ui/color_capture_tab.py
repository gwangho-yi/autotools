from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget
)
from PySide6.QtCore import Qt, Signal

from ui.color_picker import pick_pixel_color
from ui.region_select import select_region

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
    start_requested = Signal(dict, tuple, int)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_rgb: tuple[int, int, int] | None = None
        self._region: dict | None = None
        self._build_ui()

    @property
    def target_rgb(self) -> tuple[int, int, int] | None:
        return self._target_rgb

    @property
    def region(self) -> dict | None:
        return self._region

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 6)
        layout.setSpacing(10)

        # 색 샘플 행
        color_row = QHBoxLayout()
        self._pick_color_btn = QPushButton("색 지정")
        self._pick_color_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_color_btn.clicked.connect(self._on_pick_color)
        color_row.addWidget(self._pick_color_btn)
        self._swatch = QLabel()
        self._swatch.setFixedSize(40, 28)
        self._swatch.setStyleSheet("background-color: #2a2a4e; border-radius: 4px;")
        color_row.addWidget(self._swatch)

        self._rgb_spins: list[QSpinBox] = []
        for label_text in ("R", "G", "B"):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            color_row.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setStyleSheet(_SPIN_STYLE)
            spin.setFixedWidth(52)
            spin.valueChanged.connect(self._on_rgb_spin_changed)
            color_row.addWidget(spin)
            self._rgb_spins.append(spin)
        color_row.addStretch()
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

        layout.addStretch()

        # 시작/정지 스택
        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)
        self._start_btn = QPushButton("시작")
        self._start_btn.setFixedHeight(44)
        self._start_btn.setStyleSheet(_BTN_GREEN)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._btn_stack.addWidget(self._start_btn)
        self._stop_btn = QPushButton("중지")
        self._stop_btn.setFixedHeight(44)
        self._stop_btn.setStyleSheet(_BTN_RED)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        self._btn_stack.addWidget(self._stop_btn)
        layout.addWidget(self._btn_stack)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _refresh_start_enabled(self) -> None:
        self._start_btn.setEnabled(self._target_rgb is not None)

    def _on_pick_color(self) -> None:
        result = pick_pixel_color()
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
        region = select_region()
        if region is None:
            self._status_label.setText("")
            self._refresh_start_enabled()
            return
        self._region = region
        self.start_requested.emit(self._region, self._target_rgb, self._tolerance.value())

    def set_monitoring(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._pick_color_btn.setEnabled(not active)
        self._tolerance.setEnabled(not active)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
