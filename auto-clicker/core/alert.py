import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QThread

if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent.parent

_SOUND = _base / "assets" / "notify.wav"


def alert(volume: float = 1.0) -> None:
    """volume: 0.0(무음) ~ 1.0(최대). macOS afplay -v 옵션 사용."""
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", "-v", str(volume), str(_SOUND)])
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)


class AlertRepeater(QThread):
    """시퀀스 완료 후 프로그램 종료 시까지 15초 간격으로 알림음을 반복한다."""

    def __init__(self, interval_s: float = 15, parent=None):
        super().__init__(parent)
        self._interval_s = interval_s
        self.volume: float = 1.0

    def run(self) -> None:
        while not self.isInterruptionRequested():
            alert(self.volume)
            end = time.monotonic() + self._interval_s
            while time.monotonic() < end:
                if self.isInterruptionRequested():
                    return
                time.sleep(0.05)

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
