from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

from autotools_shared.alert import AlertRepeater
from autotools_shared.click_engine import ClickEngine
from autotools_shared.ipc.server import IpcServer
from autotools_shared.spinbox_style import spinbox_style
from autotools_shared.clickpoint_list import ClickPointList
from ui.capture_row import CaptureRow

_BTN_PRIMARY = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 14px; font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_DANGER = """
    QPushButton {
        background-color: transparent;
        color: #e05555; border: 1px solid #e05555;
        border-radius: 8px; font-size: 14px; font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton:hover { background-color: rgba(224,85,85,0.1); }
    QPushButton:disabled { color: #4a2a2a; border-color: #4a2a2a; }
"""

_BTN_WAITING = """
    QPushButton {
        background-color: #2a2a4e; color: #444466;
        border: none; border-radius: 8px;
        font-size: 14px; font-weight: bold;
        padding: 8px 20px;
    }
"""

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
        self._capture_row: CaptureRow | None = None
        self._capture_blocked = False
        self._engine = ClickEngine()
        self._alert_repeater = AlertRepeater()
        self._ipc = IpcServer(port=54321, parent=self)
        self._delay_timer: QTimer | None = None
        self._countdown_remaining: int = 0
        self._build_ui()
        self._update_action_btn()
        self._engine.sequence_finished.connect(
            self._on_sequence_finished, Qt.ConnectionType.QueuedConnection
        )
        self._engine.finished.connect(
            self._update_action_btn, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.motion_received.connect(
            self._on_motion_from_capture, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.client_connected.connect(
            self._on_client_connected, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.client_disconnected.connect(
            self._on_client_disconnected, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.start()
        self._center()

    def _build_ui(self) -> None:
        self.setWindowTitle("motion-clicker")
        self.setMinimumSize(650, 640)
        self.setStyleSheet("background-color: #1a1a2e;")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 20, 10, 16)

        # Header
        title = QLabel("motion-clicker")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("클릭할 포인트를 순서대로 추가하세요")
        subtitle.setStyleSheet("color: #666666; font-size: 12px;")
        root.addWidget(subtitle)

        # 공유 클릭 포인트 목록 위젯
        self._list = ClickPointList()
        self._list.changed.connect(self._update_action_btn)
        root.addWidget(self._list, stretch=1)

        # 순서 클릭 컨트롤(시작 지연 + 시작 버튼 + 상태)
        root.addWidget(self._build_clicker_page())

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

    def _build_clicker_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setSpacing(10)
        root.setContentsMargins(0, 8, 0, 0)

        # Delay start row (hidden when capture is connected)
        self._delay_row = QWidget()
        delay_layout = QHBoxLayout(self._delay_row)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        delay_layout.setSpacing(6)

        delay_lbl = QLabel("시작 지연:")
        delay_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        delay_layout.addWidget(delay_lbl)

        self._delay_h = QSpinBox()
        self._delay_h.setRange(0, 23)
        self._delay_h.setSuffix(" 시")
        self._delay_h.setFixedWidth(72)
        self._delay_h.setStyleSheet(spinbox_style())
        delay_layout.addWidget(self._delay_h)

        self._delay_m = QSpinBox()
        self._delay_m.setRange(0, 59)
        self._delay_m.setSuffix(" 분")
        self._delay_m.setFixedWidth(72)
        self._delay_m.setStyleSheet(spinbox_style())
        delay_layout.addWidget(self._delay_m)

        self._delay_s = QSpinBox()
        self._delay_s.setRange(0, 59)
        self._delay_s.setSuffix(" 초")
        self._delay_s.setFixedWidth(72)
        self._delay_s.setStyleSheet(spinbox_style())
        delay_layout.addWidget(self._delay_s)

        delay_layout.addStretch()
        root.addWidget(self._delay_row)

        root.addStretch()

        # Bottom row
        bottom = QHBoxLayout()
        self._action_btn = QPushButton("▶ 시작")
        self._action_btn.setStyleSheet(_BTN_PRIMARY)
        self._action_btn.setFixedHeight(44)
        self._action_btn.clicked.connect(self._on_action_clicked)
        bottom.addWidget(self._action_btn, stretch=1)
        root.addLayout(bottom)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666666; font-size: 11px;")
        root.addWidget(self._status_label)

        return page

    def _center(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _get_delay_seconds(self) -> int:
        return (self._delay_h.value() * 3600
                + self._delay_m.value() * 60
                + self._delay_s.value())

    def _update_action_btn(self) -> None:
        if self._delay_timer is not None:
            self._action_btn.setText("■ 취소")
            self._action_btn.setStyleSheet(_BTN_DANGER)
            self._action_btn.setEnabled(True)
        elif self._engine.isRunning():
            self._action_btn.setText("■ 중지")
            self._action_btn.setStyleSheet(_BTN_DANGER)
            self._action_btn.setEnabled(True)
        elif self._capture_row:
            text = "중지됨" if self._capture_blocked else "대기 중"
            self._action_btn.setText(text)
            self._action_btn.setStyleSheet(_BTN_WAITING)
            self._action_btn.setEnabled(False)
        else:
            self._action_btn.setText("▶ 시작")
            self._action_btn.setStyleSheet(_BTN_PRIMARY)
            self._action_btn.setEnabled(bool(self._list.count()))

    def _on_action_clicked(self) -> None:
        if self._delay_timer is not None or self._engine.isRunning():
            self._on_stop()
        else:
            self._on_start()

    def _on_client_connected(self) -> None:
        if self._capture_row is not None:
            return
        row = CaptureRow()
        self._capture_row = row
        self._list.set_index_offset(1)
        # 리스트 위젯 바로 위에 삽입
        layout = self.layout()
        idx = layout.indexOf(self._list)
        layout.insertWidget(idx, row)
        row.show()
        self._capture_blocked = False
        self._delay_row.hide()
        self._update_action_btn()
        self._status_label.setText("motion-capture 연결됨 — 신호 대기 중...")

    def _on_client_disconnected(self) -> None:
        if self._capture_row is None:
            return
        self.layout().removeWidget(self._capture_row)
        self._capture_row.deleteLater()
        self._capture_row = None
        self._list.set_index_offset(0)
        self._capture_blocked = False
        self._delay_row.show()
        self._update_action_btn()
        if not self._engine.isRunning():
            self._status_label.setText("")

    def _on_start(self) -> None:
        if not self._list.count():
            self._status_label.setText("포인트를 먼저 추가하세요.")
            return
        if self._engine.isRunning():
            return
        total_s = self._get_delay_seconds()
        if total_s > 0:
            self._start_countdown(total_s)
        else:
            self._start_engine()

    def _start_countdown(self, total_s: int) -> None:
        self._countdown_remaining = total_s
        self._delay_timer = QTimer(self)
        self._delay_timer.timeout.connect(self._on_countdown_tick)
        self._delay_row.setEnabled(False)
        self._update_action_btn()
        self._update_countdown_label()
        self._delay_timer.start(1000)

    def _on_countdown_tick(self) -> None:
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            self._stop_countdown()
            self._start_engine()
        else:
            self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        s = self._countdown_remaining
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        self._status_label.setText(f"시작까지 {h:02d}:{m:02d}:{sec:02d} 남음...")

    def _stop_countdown(self) -> None:
        if self._delay_timer is not None:
            self._delay_timer.stop()
            self._delay_timer.deleteLater()
            self._delay_timer = None
        self._delay_row.setEnabled(True)

    def _start_engine(self) -> None:
        self._engine.set_points(self._list.points())
        self._engine.start_standalone()
        self._update_action_btn()
        self._status_label.setText("실행 중...")

    def _on_stop(self) -> None:
        if self._delay_timer is not None:
            self._stop_countdown()
            self._status_label.setText("취소됨.")
            self._update_action_btn()
            return
        self._action_btn.setEnabled(False)  # wait() 블로킹 중 큐에 쌓인 클릭 차단
        self._engine.stop()
        if self._capture_row:
            self._capture_blocked = True
            self._status_label.setText("중지됨. (연결 해제 후 재시작 가능)")
        else:
            self._status_label.setText("중지됨.")
        self._update_action_btn()

    def _on_volume_changed(self, value: int) -> None:
        self._vol_pct_label.setText(f"{value}%")
        self._alert_repeater.volume = value / 100

    def _on_mute_clicked(self) -> None:
        self._alert_repeater.stop()
        self._mute_btn.hide()

    def _on_sequence_finished(self) -> None:
        if self._capture_row:
            self._status_label.setText("완료. 다음 신호 대기 중...")
        else:
            self._status_label.setText("완료.")
        self._update_action_btn()
        if not self._alert_repeater.isRunning():
            self._alert_repeater.start()
            self._mute_btn.show()

    def _on_motion_from_capture(self, _x: int, _y: int) -> None:
        if self._engine.isRunning() or self._capture_blocked:
            return
        click_type = self._capture_row.click_type if self._capture_row else "left"
        self._engine.set_points(self._list.points())
        self._engine.start_from_capture(click_type)
        self._update_action_btn()
        self._status_label.setText("motion-capture 신호 수신 → 클릭 실행 중...")

    def closeEvent(self, event) -> None:
        self._stop_countdown()
        self._ipc.stop()
        if self._engine.isRunning():
            self._engine.stop()
        if self._alert_repeater.isRunning():
            self._alert_repeater.stop()
        event.accept()
