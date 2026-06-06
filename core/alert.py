import sys
import os


def alert():
    if sys.platform == "darwin":
        os.system("afplay /System/Library/Sounds/Glass.aiff &")
    elif sys.platform == "win32":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
