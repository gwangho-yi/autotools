from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from core.models import ClickPoint
from core.click_engine import ClickEngine
from core.ipc_server import IpcServer
from ui.point_picker import pick_point
from ui.click_point_row import ClickPointRow

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

_BTN_OUTLINE = """
    QPushButton {{
        background-color: transparent;
        color: {color}; border: 1px solid {color};
        border-radius: 8px; font-size: 13px;
        padding: 8px 16px;
    }}
    QPushButton:hover {{ background-color: rgba(78,204,163,0.1); }}
    QPushButton:checked {{
        background-color: rgba(78,204,163,0.15);
        color: #4ecca3; border-color: #4ecca3;
    }}
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


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._rows: list[ClickPointRow] = []
        self._engine = ClickEngine()
        self._server: IpcServer | None = None
        self._build_ui()
        self._engine.sequence_finished.connect(self._on_sequence_finished)
        self._center()

    def _build_ui(self) -> None:
        self.setWindowTitle("auto-clicker")
        self.setMinimumSize(580, 460)
        self.setStyleSheet("background-color: #1a1a2e;")

        root = QVBoxLayout(self)
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

        # Bottom row
        bottom = QHBoxLayout()
        self._start_btn = QPushButton("▶ 시작")
        self._start_btn.setStyleSheet(_BTN_PRIMARY)
        self._start_btn.clicked.connect(self._on_start)
        bottom.addWidget(self._start_btn)
        self._stop_btn = QPushButton("■ 중지")
        self._stop_btn.setStyleSheet(_BTN_DANGER)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        bottom.addWidget(self._stop_btn)
        bottom.addStretch()
        self._connect_btn = QPushButton("auto-capture 연결")
        self._connect_btn.setCheckable(True)
        self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color="#888888"))
        self._connect_btn.clicked.connect(self._on_toggle_connect)
        bottom.addWidget(self._connect_btn)
        root.addLayout(bottom)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666666; font-size: 11px;")
        root.addWidget(self._status_label)

    def _center(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

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
        for i, r in enumerate(self._rows):
            r.set_index(i)

    def _on_start(self) -> None:
        if not self._rows:
            self._status_label.setText("포인트를 먼저 추가하세요.")
            return
        if self._engine.isRunning():
            return
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_standalone()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("실행 중...")

    def _on_stop(self) -> None:
        self._engine.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("중지됨.")

    def _on_sequence_finished(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("완료.")

    def _on_toggle_connect(self, checked: bool) -> None:
        if checked:
            self._server = IpcServer()
            self._server.motion_received.connect(self._on_motion_from_capture)
            self._server.client_connected.connect(
                lambda: self._set_connect_status("수신 중 ●", "#4ecca3")
            )
            self._server.client_disconnected.connect(
                lambda: self._set_connect_status("연결 대기 중...", "#888888")
            )
            self._server.start()
            self._set_connect_status("연결 대기 중...", "#888888")
        else:
            if self._server:
                self._server.stop()
                self._server = None
            self._connect_btn.setText("auto-capture 연결")
            self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color="#888888"))
            self._status_label.setText("")

    def _set_connect_status(self, text: str, color: str) -> None:
        self._connect_btn.setText(text)
        self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color=color))

    def _on_motion_from_capture(self, x: int, y: int) -> None:
        if self._engine.isRunning():
            return
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_from_capture()
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("auto-capture 신호 수신 → 클릭 실행 중...")

    def closeEvent(self, event) -> None:
        if self._server:
            self._server.stop()
        if self._engine.isRunning():
            self._engine.stop()
        event.accept()
