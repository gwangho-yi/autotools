"""Generate assets/icon.icns from the QPainter ticket icon."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication
from ui.launcher import make_icon_pixmap

ICONSET = Path("assets/icon.iconset")
ICNS = Path("assets/icon.icns")

SIZES = [16, 32, 128, 256, 512]


def main():
    app = QApplication(sys.argv)
    ICONSET.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        px = make_icon_pixmap(size)
        px.save(str(ICONSET / f"icon_{size}x{size}.png"))
        px2 = make_icon_pixmap(size * 2)
        px2.save(str(ICONSET / f"icon_{size}x{size}@2x.png"))

    ret = os.system(f"iconutil -c icns {ICONSET} -o {ICNS}")
    if ret != 0:
        print("iconutil failed", file=sys.stderr)
        sys.exit(1)
    print(f"Icon written to {ICNS}")


if __name__ == "__main__":
    main()
