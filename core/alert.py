import sys
import subprocess


def alert():
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif sys.platform == "win32":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    else:
        pass
