import json
import socket
from PySide6.QtCore import QThread, Signal


class IpcClient(QThread):
    motion_received = Signal(int, int)
    connected = Signal()
    disconnected = Signal()

    HOST = "127.0.0.1"
    PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False

    def run(self) -> None:
        self._running = True
        try:
            with socket.create_connection((self.HOST, self.PORT), timeout=2.0) as s:
                self.connected.emit()
                s.settimeout(1.0)
                buf = b""
                while self._running:
                    try:
                        data = s.recv(1024)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            msg = json.loads(line)
                            if msg.get("event") == "motion":
                                self.motion_received.emit(int(msg["x"]), int(msg["y"]))
                        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                            pass
        except OSError:
            pass
        finally:
            self.disconnected.emit()

    def stop(self) -> None:
        self._running = False
        self.wait()
