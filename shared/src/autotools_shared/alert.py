import io
import subprocess
import sys
import time
import wave
from pathlib import Path

from PySide6.QtCore import QThread

if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent

_SOUND = _base / "assets" / "notify.wav"


def _scaled_wav_bytes(volume: float) -> bytes | None:
    """notify.wav의 16-bit PCM 샘플을 volume(0~1)으로 스케일한 WAV 바이트를 반환.

    Windows winsound는 재생 볼륨 옵션이 없어, 진폭을 직접 줄여 메모리에서 재생한다.
    실패 시 None.
    """
    try:
        import numpy as np
        with wave.open(str(_SOUND), "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
        arr = np.frombuffer(frames, dtype=np.int16)
        v = max(0.0, min(1.0, volume))
        scaled = (arr.astype(np.float32) * v).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setparams(params)
            w.writeframes(scaled.tobytes())
        return buf.getvalue()
    except Exception:
        return None


def alert(volume: float = 1.0) -> None:
    """volume: 0.0(무음) ~ 1.0(최대)."""
    v = max(0.0, min(1.0, volume))
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", "-v", str(v), str(_SOUND)])
    elif sys.platform == "win32":
        import winsound
        if v >= 0.999:
            winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME)
            return
        data = _scaled_wav_bytes(v)
        if data is not None:
            winsound.PlaySound(data, winsound.SND_MEMORY)
        elif v > 0:
            # 스케일 실패 시 최후수단: 원음 재생
            winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME)
        # v == 0 이고 스케일 실패면 무음(재생 안 함)


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
