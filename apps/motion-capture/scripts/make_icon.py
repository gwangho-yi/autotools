"""Generate assets/icon.icns (macOS), assets/icon.ico (Windows), assets/arrow-*.png."""
import os
import sys
import struct
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from ui.launcher import make_icon_pixmap

ASSETS = Path("assets")
ICONSET = ASSETS / "icon.iconset"
ICNS = ASSETS / "icon.icns"
ICO = ASSETS / "icon.ico"

ICNS_SIZES = [16, 32, 128, 256, 512]
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def _write_ico(png_paths: list[Path], output: Path) -> None:
    images = []
    for path in png_paths:
        data = path.read_bytes()
        w = struct.unpack(">I", data[16:20])[0]
        h = struct.unpack(">I", data[20:24])[0]
        images.append((w, h, data))

    n = len(images)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + 16 * n

    dir_entries = b""
    image_data = b""
    for w, h, data in images:
        bw = 0 if w >= 256 else w
        bh = 0 if h >= 256 else h
        dir_entries += struct.pack("<BBBBHHII", bw, bh, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        image_data += data

    output.write_bytes(header + dir_entries + image_data)


def _make_arrow_png(up: bool) -> bytes:
    """9×6 RGBA PNG 삼각형 화살표 (Qt stylesheet image에 사용)."""
    w, h = 9, 6
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            cx = (w - 1) / 2
            ratio = y / (h - 1) if up else (h - 1 - y) / (h - 1)
            if abs(x - cx) <= ratio * cx + 0.5:
                row += bytearray([170, 170, 170, 255])
            else:
                row += bytearray([0, 0, 0, 0])
        rows.append(bytes(row))
    comp = zlib.compress(b"".join(rows))
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp)
            + chunk(b"IEND", b""))


def main():
    app = QApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)
    ICONSET.mkdir(parents=True, exist_ok=True)

    all_sizes = sorted(set(ICNS_SIZES + ICO_SIZES))
    png_files: dict[int, Path] = {}
    for size in all_sizes:
        px = make_icon_pixmap(size)
        path = ICONSET / f"icon_{size}x{size}.png"
        px.save(str(path))
        png_files[size] = path

    for size in ICNS_SIZES:
        if size <= 512:
            px2 = make_icon_pixmap(size * 2)
            px2.save(str(ICONSET / f"icon_{size}x{size}@2x.png"))

    if sys.platform == "darwin":
        ret = os.system(f"iconutil -c icns {ICONSET} -o {ICNS}")
        if ret != 0:
            print("iconutil failed", file=sys.stderr)
            sys.exit(1)
        print(f"Icon written to {ICNS}")

    ico_pngs = [png_files[s] for s in ICO_SIZES if s in png_files]
    _write_ico(ico_pngs, ICO)
    print(f"Icon written to {ICO}")

    (ASSETS / "arrow-up.png").write_bytes(_make_arrow_png(up=True))
    (ASSETS / "arrow-down.png").write_bytes(_make_arrow_png(up=False))
    print("Arrow PNGs written to assets/")


if __name__ == "__main__":
    main()
