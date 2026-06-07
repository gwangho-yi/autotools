import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent.parent

_SOUND = _base / "assets" / "notify.wav"
_CLICKER_PORT = 54321


def _send_to_clicker(x: int, y: int) -> None:
    try:
        with socket.create_connection(("localhost", _CLICKER_PORT), timeout=0.1) as s:
            msg = json.dumps({"event": "motion", "x": x, "y": y}) + "\n"
            s.sendall(msg.encode())
    except OSError:
        pass


def alert(x: int = 0, y: int = 0) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", str(_SOUND)])
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)
    threading.Thread(target=_send_to_clicker, args=(x, y), daemon=True).start()
