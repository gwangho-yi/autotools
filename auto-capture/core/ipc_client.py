import json
import socket
import threading
from PySide6.QtCore import QThread, Signal


class IpcClient(QThread):
    connected = Signal()
    disconnected = Signal()

    HOST = "127.0.0.1"
    PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def send_motion(self, x: int, y: int) -> None:
        msg = (json.dumps({"event": "motion", "x": x, "y": y}) + "\n").encode()
        with self._lock:
            if self._sock:
                try:
                    self._sock.sendall(msg)
                except OSError:
                    pass

    def send_color_match(self, x: int, y: int) -> None:
        msg = (json.dumps({"event": "color_match", "x": x, "y": y}) + "\n").encode()
        with self._lock:
            if self._sock:
                try:
                    self._sock.sendall(msg)
                except OSError:
                    pass

    def run(self) -> None:
        self._running = True
        try:
            with socket.create_connection((self.HOST, self.PORT), timeout=2.0) as s:
                s.settimeout(1.0)
                with self._lock:
                    self._sock = s
                self.connected.emit()
                while self._running:
                    try:
                        data = s.recv(1)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                with self._lock:
                    self._sock = None
        except OSError:
            pass
        finally:
            self.disconnected.emit()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass
        self.wait()
