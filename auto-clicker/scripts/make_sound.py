"""Generate assets/notify.wav - a three-tone ascending melody (C5→E5→G5)."""
import wave
import math
import struct
from pathlib import Path

ASSETS = Path("assets")
OUTPUT = ASSETS / "notify.wav"
SAMPLE_RATE = 44100

NOTES = [
    (523.25, 0.15, 0.9),  # C5
    (659.25, 0.15, 0.9),  # E5
    (783.99, 0.25, 0.85), # G5
]


def main():
    ASSETS.mkdir(exist_ok=True)
    frames = []
    for freq, duration, vol in NOTES:
        n = int(SAMPLE_RATE * duration)
        for i in range(n):
            t = i / SAMPLE_RATE
            env = math.exp(-t * 8) * vol
            sample = int(env * math.sin(2 * math.pi * freq * t) * 32767 * 1.5)
            frames.append(max(-32767, min(32767, sample)))
    with wave.open(str(OUTPUT), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(struct.pack(f"<{len(frames)}h", *frames))
    print(f"Sound written to {OUTPUT}")


if __name__ == "__main__":
    main()
