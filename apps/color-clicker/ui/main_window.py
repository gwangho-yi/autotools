from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from pynput import keyboard

from autotools_shared.alert import AlertRepeater
from autotools_shared.click_engine import ClickEngine
from autotools_shared.continuous_click_engine import ContinuousClickEngine
from autotools_shared.ipc.server import IpcServer
from autotools_shared.hotkey import HotkeyRelay
from autotools_shared.clickpoint_list import ClickPointList
from ui.color_clicker_tab import ColorClickerTab

_BTN_MUTE = """
    QPushButton {
        background-color: transparent;
        color: #f0a500; border: 1px solid #f0a500;
        border-radius: 8px; font-size: 14px; font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton:hover { background-color: rgba(240,165,0,0.1); }
"""


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._engine = ClickEngine()
        self._continuous: ContinuousClickEngine | None = None
        self._alert_repeater = AlertRepeater()
        self._ipc = IpcServer(port=54322, parent=self)
        self._build_ui()
        self._engine.sequence_finished.connect(
            self._on_sequence_finished, Qt.ConnectionType.QueuedConnection
        )
        self.color_tab.start_requested.connect(self._on_color_start)
        self.color_tab.stop_requested.connect(self._on_color_stop)
        self._ipc.color_match_received.connect(
            self._on_color_match, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.start()
        self._f6_relay = HotkeyRelay(self._on_f6_toggle)
        self._hotkey_listener = keyboard.GlobalHotKeys({'<ctrl>+<f7>': self._f6_relay.notify})
        self._hotkey_listener.start()
        self._center()

    def _build_ui(self) -> None:
        self.setWindowTitle("color-clicker")
        self.setMinimumSize(480, 835)
        self.resize(480, 850)
        self.setStyleSheet("background-color: #1a1a2e;")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 20, 10, 16)

        # Header
        title = QLabel("color-clicker")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("지정 색 감지 시 연속 클릭을 멈추고 시퀀스를 실행합니다")
        subtitle.setStyleSheet("color: #666666; font-size: 12px;")
        root.addWidget(subtitle)

        # 공유 클릭 포인트 목록 위젯
        self._list = ClickPointList()
        root.addWidget(self._list)

        # 컬러 클릭 컨트롤(연속 클릭 지점 + min/max + 시작/중지)
        self.color_tab = ColorClickerTab()
        root.addWidget(self.color_tab)

        # 알림음 컨트롤(음소거 버튼 + 볼륨)
        mute_row = QHBoxLayout()
        self._mute_btn = QPushButton("🔔 알림 중지")
        self._mute_btn.setStyleSheet(_BTN_MUTE)
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        self._mute_btn.hide()
        mute_row.addWidget(self._mute_btn)
        mute_row.addStretch()
        root.addLayout(mute_row)

        vol_row = QHBoxLayout()
        vol_label = QLabel("볼륨:")
        vol_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        vol_label.setFixedWidth(36)
        vol_row.addWidget(vol_label)
        self._vol_slider = QSlider(Qt.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(100)
        self._vol_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #2a2a4e; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #4ecca3; border-radius: 2px; }
            QSlider::handle:horizontal {
                width: 12px; height: 12px; margin: -4px 0;
                background: #4ecca3; border-radius: 6px;
            }
        """)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self._vol_slider)
        self._vol_pct_label = QLabel("100%")
        self._vol_pct_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self._vol_pct_label.setFixedWidth(36)
        vol_row.addWidget(self._vol_pct_label)
        root.addLayout(vol_row)
        root.addStretch()

    def _center(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _on_color_start(self) -> None:
        if not self.color_tab.points:
            return
        if self._engine.isRunning():
            return
        if self._continuous is not None and self._continuous.isRunning():
            return
        self._continuous = ContinuousClickEngine(
            self.color_tab.points, self.color_tab.min_ms, self.color_tab.max_ms,
            self.color_tab.click_type, loop=self.color_tab.loop,
        )
        self._continuous.start()
        self.color_tab.set_running(True)
        self.color_tab.set_status("연속 클릭 중... (컬러 감지 대기)")

    def _on_color_stop(self) -> None:
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        self.color_tab.set_running(False)
        self.color_tab.set_status("중지됨.")

    def _on_color_match(self, x: int, y: int) -> None:
        # 이미 시퀀스 실행 중이면 무시(상호배타)
        if self._engine.isRunning():
            return
        # 연속 클릭 정지 후 감지 좌표 클릭 → 기존 포인트 시퀀스
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        self.color_tab.set_running(False)
        self._engine.set_points(self._list.points())
        self._engine.start_from_color(x, y, self.color_tab.click_type)
        self.color_tab.set_status(f"감지 ({x}, {y}) → 클릭 시퀀스 실행 중...")

    def _on_f6_toggle(self) -> None:
        if self._engine.isRunning():
            return
        if self._continuous is not None and self._continuous.isRunning():
            self._on_color_stop()
        elif self.color_tab.points:
            self._on_color_start()

    def _on_volume_changed(self, value: int) -> None:
        self._vol_pct_label.setText(f"{value}%")
        self._alert_repeater.volume = value / 100

    def _on_mute_clicked(self) -> None:
        self._alert_repeater.stop()
        self._mute_btn.hide()

    def _on_sequence_finished(self) -> None:
        self.color_tab.set_status("완료.")
        if not self._alert_repeater.isRunning():
            self._alert_repeater.start()
            self._mute_btn.show()

    def closeEvent(self, event) -> None:
        self._hotkey_listener.stop()
        self._ipc.stop()
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        if self._engine.isRunning():
            self._engine.stop()
        if self._alert_repeater.isRunning():
            self._alert_repeater.stop()
        event.accept()
