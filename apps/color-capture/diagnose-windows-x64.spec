# -*- mode: python ; coding: utf-8 -*-
# 진단 도구 전용 빌드. 대상 PC에 Python이 없을 수 있어 단독 exe로 뽑는다.
# 콘솔 출력이 결과물이므로 console=True 이어야 한다.
from PyInstaller.utils.hooks import collect_all

numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')
mss_datas, mss_binaries, mss_hiddenimports = collect_all('mss')
shared_datas, shared_binaries, shared_hiddenimports = collect_all('autotools_shared')

a = Analysis(
    ['scripts/diagnose.py'],
    pathex=['.'],
    binaries=numpy_binaries + mss_binaries + shared_binaries,
    datas=numpy_datas + mss_datas + shared_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'core.color_monitor',
    ] + numpy_hiddenimports + mss_hiddenimports + shared_hiddenimports,
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
    name='color-capture-diagnose',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch='x86_64',
)
