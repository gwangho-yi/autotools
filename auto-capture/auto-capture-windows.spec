# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
mss_datas, mss_binaries, mss_hiddenimports = collect_all('mss')
pynput_datas, pynput_binaries, pynput_hiddenimports = collect_all('pynput')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[] + numpy_binaries + mss_binaries + pynput_binaries,
    datas=[('assets', 'assets')] + numpy_datas + mss_datas + pynput_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
    ] + numpy_hiddenimports + mss_hiddenimports + pynput_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='auto-capture',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch='arm64',
    icon='assets/icon.ico',
)
