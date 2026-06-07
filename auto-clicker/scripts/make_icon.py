"""Generate assets/icon.icns (macOS) and assets/icon.ico (Windows)."""
import os
import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap

ASSETS = Path("assets")
ICONSET = ASSETS / "icon.iconset"
ICNS = ASSETS / "icon.icns"
ICO = ASSETS / "icon.ico"

ICNS_SIZES = [16, 32, 128, 256, 512]
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def make_icon_pixmap(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    stroke = max(2, int(size * 0.06))
    pen = QPen(QColor("#4ecca3"), stroke)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    margin = max(2, int(size * 0.1))
    w = size - 2 * margin
    h = int(size * 0.55)
    y = int(size * 0.2)
    radius = max(2, int(size * 0.08))

    # 티켓 외곽
    p.drawRoundedRect(margin, y, w, h, radius, radius)

    # 좌우 반원 노치
    notch_r = max(2, int(size * 0.07))
    notch_y = y + h // 2
    p.setBrush(QColor("#1a1a2e"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(margin - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)
    p.drawEllipse(margin + w - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)

    # 점선 구분선
    dash_pen = QPen(QColor("#4ecca3"), max(1, int(size * 0.04)), Qt.DashLine)
    p.setPen(dash_pen)
    p.drawLine(margin + notch_r, notch_y, margin + w - notch_r, notch_y)

    p.end()
    return px


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


if __name__ == "__main__":
    main()
