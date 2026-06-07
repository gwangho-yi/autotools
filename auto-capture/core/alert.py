import sys
import subprocess
from pathlib import Path

if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent.parent

_SOUND = _base / "assets" / "notify.wav"


def alert():
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", str(_SOUND)])
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)
