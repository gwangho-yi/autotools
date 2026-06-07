import json
import os
import signal
import socket
import subprocess
from PySide6.QtCore import QThread, Signal


class IpcServer(QThread):
    motion_received = Signal(int, int)
    client_connected = Signal()
    client_disconnected = Signal()

    PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._sock: socket.socket | None = None

    def _free_port(self) -> None:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self.PORT}"],
                capture_output=True, text=True
            )
            for pid_str in result.stdout.strip().split():
                try:
                    os.kill(int(pid_str), signal.SIGTERM)
                except (ProcessLookupError, ValueError):
                    pass
        except Exception:
            pass

    def run(self) -> None:
        self._running = True
        self._free_port()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("127.0.0.1", self.PORT))
            self._sock.listen(1)
            self._sock.settimeout(1.0)
            print(f"[IpcServer] listening on port {self.PORT}", flush=True)
        except OSError as e:
            print(f"[IpcServer] bind failed: {e}", flush=True)
            self._running = False
            return

        while self._running:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            print(f"[IpcServer] client connected from {addr}", flush=True)
            self.client_connected.emit()
            self._handle(conn)
            print("[IpcServer] client disconnected", flush=True)
            self.client_disconnected.emit()

        try:
            self._sock.close()
        except OSError:
            pass

    def _handle(self, conn: socket.socket) -> None:
        buf = b""
        conn.settimeout(1.0)
        while self._running:
            try:
                data = conn.recv(1024)
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
        conn.close()

    def stop(self) -> None:
        self._running = False
        self.wait()
