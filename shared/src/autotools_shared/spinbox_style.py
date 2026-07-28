import sys
from pathlib import Path


def spinbox_style() -> str:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    up = (base / "assets" / "arrow-up.png").as_posix()
    dn = (base / "assets" / "arrow-down.png").as_posix()
    return f"""
    QSpinBox {{
        background-color: #2a2a4e; color: #cccccc;
        border: 1px solid #3a3a6e; border-radius: 4px;
        font-size: 13px; padding: 2px 4px;
    }}
    QSpinBox:disabled {{ color: #444466; border-color: #2a2a4e; }}
    QSpinBox::up-button {{
        width: 18px; subcontrol-origin: border; subcontrol-position: top right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::down-button {{
        width: 18px; subcontrol-origin: border; subcontrol-position: bottom right;
        background-color: #3a3a6e; border-left: 1px solid #4a4a7e;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background-color: #4a4a8e; }}
    QSpinBox::up-arrow {{ image: url("{up}"); width: 9px; height: 6px; }}
    QSpinBox::down-arrow {{ image: url("{dn}"); width: 9px; height: 6px; }}
    """
