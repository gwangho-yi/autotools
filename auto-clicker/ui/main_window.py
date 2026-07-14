import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QApplication, QSlider, QSpinBox, QTabWidget
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication


def _spinbox_style() -> str:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    up = (base / "assets" / "arrow-up.png").as_posix()
    dn = (base / "assets" / "arrow-down.png").as_posix()
    return f"""
    QSpinBox {{
        background-color: #2a2a4e; color: #cccccc;
        border: 1px solid #3a3a6e; border-radius: 4px;
        font-size: 13px; padding: 2px 4px;
    }}
    QSpinBox:disabled {{ color: #444466; border-color: #2a2a4e; }}
    QSpinBox::up-button {{
        width: 18px; subcontrol-origin: border; subcontrol-position: top right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::down-button {{
        width: 18px; subcontrol-origin: border; subcontrol-position: bottom right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background-color: #4a4a8e; }}
    QSpinBox::up-arrow {{ image: url("{up}"); width: 9px; height: 6px; }}
    QSpinBox::down-arrow {{ image: url("{dn}"); width: 9px; height: 6px; }}
    """

from core.alert import AlertRepeater
from core.models import ClickPoint
from core.click_engine import ClickEngine
from core.continuous_click_engine import ContinuousClickEngine
from core.ipc_server import IpcServer
from ui.point_picker import pick_point
from ui.click_point_row import ClickPointRow
from ui.capture_row import CaptureRow
from ui.color_clicker_tab import ColorClickerTab

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

_BTN_ADD = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
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
        self._rows: list[ClickPointRow] = []
        self._capture_row: CaptureRow | None = None
        self._capture_blocked = False
        self._engine = ClickEngine()
        self._continuous: ContinuousClickEngine | None = None
        self._alert_repeater = AlertRepeater()
        self._ipc = IpcServer(self)
        self._delay_timer: QTimer | None = None
        self._countdown_remaining: int = 0
        self._build_ui()
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
        self.color_tab.start_requested.connect(self._on_color_start)
        self.color_tab.stop_requested.connect(self._on_color_stop)
        self._ipc.color_match_received.connect(
            self._on_color_match, Qt.ConnectionType.QueuedConnection
        )
        self._ipc.start()
        self._center()

    def _build_ui(self) -> None:
        self.setWindowTitle("auto-clicker")
        self.setMinimumSize(650, 520)
        self.setStyleSheet("background-color: #1a1a2e;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #2a2a4e; color: #888888;
                padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #4ecca3; color: #1a1a2e; font-weight: bold; }
        """)
        tabs.addTab(self._build_clicker_page(), "순서 클릭")
        self.color_tab = ColorClickerTab()
        tabs.addTab(self.color_tab, "컬러 클리커")
        outer.addWidget(tabs)

    def _build_clicker_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setSpacing(10)
        root.setContentsMargins(20, 20, 20, 16)

        # Header
        title = QLabel("auto-clicker")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("클릭할 포인트를 순서대로 추가하세요")
        subtitle.setStyleSheet("color: #666666; font-size: 12px;")
        root.addWidget(subtitle)

        # Column header labels
        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 8, 0)
        for text, width in [("#", 26), ("위치", 108), ("딜레이 (h/m/s/ms)", 230), ("종류", 103)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet("color: #444466; font-size: 11px;")
            header.addWidget(lbl)
        header.addStretch()
        root.addLayout(header)

        # Scrollable list
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
        root.addWidget(scroll, stretch=1)

        # Add point button
        self._add_btn = QPushButton("+ 포인트 추가")
        self._add_btn.setStyleSheet(_BTN_ADD)
        self._add_btn.clicked.connect(self._on_add_point)
        root.addWidget(self._add_btn)

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
        self._delay_h.setStyleSheet(_spinbox_style())
        delay_layout.addWidget(self._delay_h)

        self._delay_m = QSpinBox()
        self._delay_m.setRange(0, 59)
        self._delay_m.setSuffix(" 분")
        self._delay_m.setFixedWidth(72)
        self._delay_m.setStyleSheet(_spinbox_style())
        delay_layout.addWidget(self._delay_m)

        self._delay_s = QSpinBox()
        self._delay_s.setRange(0, 59)
        self._delay_s.setSuffix(" 초")
        self._delay_s.setFixedWidth(72)
        self._delay_s.setStyleSheet(_spinbox_style())
        delay_layout.addWidget(self._delay_s)

        delay_layout.addStretch()
        root.addWidget(self._delay_row)

        # Bottom row
        bottom = QHBoxLayout()
        self._action_btn = QPushButton("▶ 시작")
        self._action_btn.setStyleSheet(_BTN_PRIMARY)
        self._action_btn.clicked.connect(self._on_action_clicked)
        bottom.addWidget(self._action_btn)
        self._mute_btn = QPushButton("🔔 알림 중지")
        self._mute_btn.setStyleSheet(_BTN_MUTE)
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        self._mute_btn.hide()
        bottom.addWidget(self._mute_btn)
        bottom.addStretch()
        root.addLayout(bottom)

        # Volume row
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

    def _on_add_point(self) -> None:
        self.hide()
        QApplication.processEvents()
        result = pick_point()
        self.show()
        self.raise_()
        self.activateWindow()
        if result is None:
            return
        x, y = result
        point = ClickPoint(x=x, y=y)
        row = ClickPointRow(len(self._rows), point)
        row.delete_requested.connect(self._on_delete_row)
        row.pick_position_requested.connect(self._on_pick_position)
        self._rows.append(row)
        self._list_layout.addWidget(row)
        self._renumber_rows()

    def _on_pick_position(self, row: ClickPointRow) -> None:
        self.hide()
        QApplication.processEvents()
        result = pick_point()
        self.show()
        self.raise_()
        self.activateWindow()
        if result is None:
            return
        x, y = result
        row.set_position(x, y)

    def _on_delete_row(self, row: ClickPointRow) -> None:
        self._rows.remove(row)
        self._list_layout.removeWidget(row)
        row.deleteLater()
        self._renumber_rows()

    def _renumber_rows(self) -> None:
        offset = 1 if self._capture_row else 0
        for i, r in enumerate(self._rows):
            r.set_index(i + offset)

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
            self._action_btn.setEnabled(True)

    def _on_action_clicked(self) -> None:
        if self._delay_timer is not None or self._engine.isRunning():
            self._on_stop()
        else:
            self._on_start()

    def _on_client_connected(self) -> None:
        print("[MainWindow] _on_client_connected called", flush=True)
        if self._capture_row is not None:
            return
        row = CaptureRow()
        self._capture_row = row
        self._list_layout.insertWidget(0, row)
        row.show()
        self._renumber_rows()
        self._capture_blocked = False
        self._delay_row.hide()
        self._update_action_btn()
        self._status_label.setText("auto-capture 연결됨 — 신호 대기 중...")

    def _on_client_disconnected(self) -> None:
        if self._capture_row is None:
            return
        self._list_layout.removeWidget(self._capture_row)
        self._capture_row.deleteLater()
        self._capture_row = None
        self._renumber_rows()
        self._capture_blocked = False
        self._delay_row.show()
        self._update_action_btn()
        if not self._engine.isRunning():
            self._status_label.setText("")

    def _on_start(self) -> None:
        if not self._rows:
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
        self._engine.set_points([r.point for r in self._rows])
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

    def _on_color_start(self) -> None:
        if self.color_tab.point is None:
            return
        if self._engine.isRunning():
            return
        if self._continuous is not None and self._continuous.isRunning():
            return
        x, y = self.color_tab.point
        self._continuous = ContinuousClickEngine(
            x, y, self.color_tab.min_ms, self.color_tab.max_ms,
            self.color_tab.click_type,
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
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_from_color(x, y, self.color_tab.click_type)
        self.color_tab.set_status(f"감지 ({x}, {y}) → 클릭 시퀀스 실행 중...")

    def _on_motion_from_capture(self, _x: int, _y: int) -> None:
        if self._engine.isRunning() or self._capture_blocked:
            return
        click_type = self._capture_row.click_type if self._capture_row else "left"
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_from_capture(click_type)
        self._update_action_btn()
        self._status_label.setText("auto-capture 신호 수신 → 클릭 실행 중...")

    def closeEvent(self, event) -> None:
        self._stop_countdown()
        self._ipc.stop()
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        if self._engine.isRunning():
            self._engine.stop()
        if self._alert_repeater.isRunning():
            self._alert_repeater.stop()
        event.accept()
