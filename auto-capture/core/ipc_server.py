import json
import socket
import threading
from PySide6.QtCore import QThread


class IpcServer(QThread):
    """Persistent TCP server: pushes motion events to connected auto-clicker clients."""

    PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server_sock: socket.socket | None = None

    def send_motion(self, x: int, y: int) -> None:
        msg = (json.dumps({"event": "motion", "x": x, "y": y}) + "\n").encode()
        with self._lock:
            dead = [c for c in self._clients if not self._try_send(c, msg)]
            for c in dead:
                self._clients.remove(c)

    def _try_send(self, conn: socket.socket, data: bytes) -> bool:
        try:
            conn.sendall(data)
            return True
        except OSError:
            try:
                conn.close()
            except OSError:
                pass
            return False

    def run(self) -> None:
        self._running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_sock.bind(("127.0.0.1", self.PORT))
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
        except OSError:
            return

        while self._running:
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                self._clients.append(conn)

        with self._lock:
            for c in self._clients:
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()
        try:
            self._server_sock.close()
        except OSError:
            pass

    def stop(self) -> None:
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        self.wait()
