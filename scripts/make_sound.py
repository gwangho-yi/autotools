"""Generate assets/notify.wav - a short ping notification sound."""
import wave
import math
import struct
from pathlib import Path

ASSETS = Path("assets")
OUTPUT = ASSETS / "notify.wav"
SAMPLE_RATE = 44100
DURATION = 0.18
FREQUENCY = 880


def main():
    ASSETS.mkdir(exist_ok=True)
    n = int(SAMPLE_RATE * DURATION)
    frames = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 22)
        v = env * (math.sin(2 * math.pi * FREQUENCY * t) + 0.4 * math.sin(2 * math.pi * FREQUENCY * 2 * t))
        v = v / 1.4
        frames.append(int(v * 32767))
    with wave.open(str(OUTPUT), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(struct.pack(f"<{n}h", *frames))
    print(f"Sound written to {OUTPUT}")


if __name__ == "__main__":
    main()
