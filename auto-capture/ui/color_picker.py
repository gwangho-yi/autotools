import sys

import numpy as np
import mss
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QEventLoop, QPoint, QObject, QEvent, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication, QImage, QCursor

_LOUPE_SRC = 15        # 캡처할 원본 영역 한 변(px)
_LOUPE_SCALE = 8       # 확대 배율
_LOUPE_PANEL = _LOUPE_SRC * _LOUPE_SCALE  # 120px
_PANEL_MARGIN = 20     # 커서와 패널 사이 여백
_TEXT_H = 22           # 하단 RGB 텍스트 영역 높이


def _loupe_geometry(cursor_x: int, panel_w: int, screen_w: int) -> int:
    """돋보기 패널 좌상단 x 좌표. 기본은 커서 오른쪽, 우측 여유 없으면 왼쪽 flip."""
    right_x = cursor_x + _PANEL_MARGIN
    if right_x + panel_w <= screen_w:
        return right_x
    return max(0, cursor_x - _PANEL_MARGIN - panel_w)


class _EscFilter(QObject):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._callback()
            return True
        return False


class _EscRelay(QObject):
    """pynput 스레드 → Qt 메인 스레드 안전 브릿지 (Windows 전용)."""

    _sig = Signal()

    def __init__(self, callback):
        super().__init__()
        self._sig.connect(callback, Qt.ConnectionType.QueuedConnection)

    def notify(self):
        self._sig.emit()


class _ColorPickerOverlay(QWidget):
    def __init__(self, screen, shared: dict):
        super().__init__()
        self._screen = screen
        self._shared = shared
        self._global_pos = QCursor.pos()
        self._cursor_pos = QPoint(0, 0)
        self._loupe_img: QImage | None = None
        self._center_rgb = (0, 0, 0)

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.show()
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

    def mouseMoveEvent(self, event):
        self._sync_cursor_pos(event)
        self._update_loupe()
        self.update()

    def _sync_cursor_pos(self, event) -> None:
        # QCursor.pos()는 "지금 이 순간" 시스템에 다시 묻는 라이브 조회라서, 이벤트가
        # 큐에 있다가 처리되는 사이의 시간차 때문에 실제 이 이벤트가 발생한 시점의
        # 좌표와 어긋날 수 있다(작은 타겟을 정밀하게 클릭할 때처럼 클릭 직전 미세한
        # 움직임이 있으면 특히 그렇다). event.globalPosition()은 이 이벤트 자체가
        # 발생한 시점에 박제된 전역 좌표라 항상 정확하고, 로컬 좌표+화면 원점을 직접
        # 계산할 필요도 없어 멀티 모니터 환경에서도 안전하다.
        self._global_pos = event.globalPosition().toPoint()
        self._cursor_pos = self.mapFromGlobal(self._global_pos)

    def _update_loupe(self):
        gx = self._global_pos.x()
        gy = self._global_pos.y()
        half = _LOUPE_SRC // 2
        region = {"left": gx - half, "top": gy - half,
                  "width": _LOUPE_SRC, "height": _LOUPE_SRC}
        try:
            with mss.mss() as sct:
                raw = np.array(sct.grab(region))[:, :, :3]  # BGR
        except Exception:
            return  # 경계 근처 캡처 실패 → 조용히 스킵, 다음 move에서 재시도
        if raw.shape[0] != _LOUPE_SRC or raw.shape[1] != _LOUPE_SRC:
            return
        b, g, r = int(raw[half, half, 0]), int(raw[half, half, 1]), int(raw[half, half, 2])
        self._center_rgb = (r, g, b)
        # BGR → RGB 후 QImage 생성, nearest-neighbor 8배 확대
        rgb = raw[:, :, ::-1].copy()
        img = QImage(rgb.data, _LOUPE_SRC, _LOUPE_SRC,
                     3 * _LOUPE_SRC, QImage.Format_RGB888)
        self._loupe_img = img.scaled(_LOUPE_PANEL, _LOUPE_PANEL,
                                     Qt.IgnoreAspectRatio, Qt.FastTransformation)

    def paintEvent(self, event):
        p = QPainter(self)
        # 주의: 이 창은 실제 화면에 렌더링되는 반투명 창이라, 여기서 그리는 모든 것이
        # mss.grab()의 캡처 대상에 실제 픽셀처럼 함께 찍힌다. 전체화면을 덮는 딤이나
        # 십자선처럼 캡처 영역과 겹치는 장식은 절대 그리지 않는다(색 샘플링 오염 방지).

        x = self._cursor_pos.x()
        y = self._cursor_pos.y()

        hint = "클릭하여 색 지정  |  ESC 취소"
        p.setPen(QColor(255, 255, 255, 200))
        hint_font = QFont()
        hint_font.setPixelSize(14)
        p.setFont(hint_font)
        p.drawText(self.width() // 2 - 110, 32, hint)

        if self._loupe_img is not None:
            panel_h = _LOUPE_PANEL + _TEXT_H
            px = _loupe_geometry(x, _LOUPE_PANEL, self.width())
            py = max(0, min(y - _LOUPE_PANEL // 2, self.height() - panel_h))
            # 패널 배경
            p.setBrush(QColor(15, 15, 30, 230))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(px - 2, py - 2, _LOUPE_PANEL + 4, panel_h + 4, 6, 6)
            # 확대 이미지
            p.drawImage(QRect(px, py, _LOUPE_PANEL, _LOUPE_PANEL), self._loupe_img)
            # 중앙 픽셀 강조 테두리
            cell = _LOUPE_SCALE
            cx = px + (_LOUPE_SRC // 2) * cell
            cy = py + (_LOUPE_SRC // 2) * cell
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#4ecca3"), 2))
            p.drawRect(cx, cy, cell, cell)
            # RGB 텍스트
            r, g, b = self._center_rgb
            p.setPen(QColor("#cccccc"))
            txt_font = QFont()
            txt_font.setPixelSize(12)
            p.setFont(txt_font)
            p.drawText(px, py + _LOUPE_PANEL, _LOUPE_PANEL, _TEXT_H,
                       Qt.AlignCenter, f"RGB({r}, {g}, {b})")

    def mousePressEvent(self, event):
        # event.globalPosition()으로 동기화한다 — 이벤트 발생 시점에 박제된 좌표라
        # QCursor.pos()의 라이브 재조회로 인한 시간차 오차가 없다.
        self._sync_cursor_pos(event)
        self._update_loupe()
        self._shared["result"] = (
            self._global_pos.x(), self._global_pos.y(), self._center_rgb
        )
        self._shared["close_fn"]()


def pick_pixel_color() -> tuple[int, int, tuple[int, int, int]] | None:
    """풀스크린 오버레이로 픽셀 색을 샘플링. (글로벌x, 글로벌y, (r,g,b)) 반환, ESC시 None."""
    print("[DEBUG] pick_pixel_color: enter", flush=True)
    loop = QEventLoop()
    shared: dict = {"result": None, "loop": loop, "widgets": [],
                    "close_fn": None, "_closed": False, "_esc_filter": None,
                    "_kb_listener": None, "_relay": None}

    def close_all():
        if shared["_closed"]:
            return
        shared["_closed"] = True
        if shared["_kb_listener"] is not None:
            try:
                shared["_kb_listener"].stop()
            except Exception:
                pass
        app = QApplication.instance()
        if app and shared["_esc_filter"]:
            app.removeEventFilter(shared["_esc_filter"])
        for w in shared["widgets"]:
            w.close()
        loop.quit()

    shared["close_fn"] = close_all
    esc_filter = _EscFilter(close_all)
    shared["_esc_filter"] = esc_filter
    QApplication.instance().installEventFilter(esc_filter)
    print("[DEBUG] pick_pixel_color: qt esc filter installed", flush=True)

    # pynput 키보드 리스너는 Windows 전용.
    # macOS에서 pynput은 TSMGetInputSourceProperty를 백그라운드 스레드에서
    # 호출해 크래시 발생 → macOS/Linux는 Qt 이벤트 필터만 사용.
    if sys.platform == "win32":
        print("[DEBUG] pick_pixel_color: win32 branch entered", flush=True)
        try:
            from pynput import keyboard as _kb
            print("[DEBUG] pick_pixel_color: pynput.keyboard imported", flush=True)

            relay = _EscRelay(close_all)
            shared["_relay"] = relay
            print("[DEBUG] pick_pixel_color: _EscRelay created", flush=True)

            def _on_press(key):
                if key == _kb.Key.esc:
                    relay.notify()
                    return False

            listener = _kb.Listener(on_press=_on_press)
            print("[DEBUG] pick_pixel_color: about to start pynput Listener", flush=True)
            listener.start()
            print("[DEBUG] pick_pixel_color: pynput Listener started", flush=True)
            shared["_kb_listener"] = listener
        except Exception as e:
            print("[DEBUG] pick_pixel_color: win32 esc listener setup FAILED:", repr(e), flush=True)

    print("[DEBUG] pick_pixel_color: creating overlays for", len(QGuiApplication.screens()), "screen(s)", flush=True)
    for i, screen in enumerate(QGuiApplication.screens()):
        print(f"[DEBUG] pick_pixel_color: creating overlay {i} for screen {screen.name()!r}", flush=True)
        overlay = _ColorPickerOverlay(screen, shared)
        shared["widgets"].append(overlay)
        print(f"[DEBUG] pick_pixel_color: overlay {i} created", flush=True)

    print("[DEBUG] pick_pixel_color: entering loop.exec()", flush=True)
    loop.exec()
    print("[DEBUG] pick_pixel_color: loop.exec() returned, result =", shared["result"], flush=True)
    return shared["result"]
