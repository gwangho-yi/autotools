# -*- mode: python ; coding: utf-8 -*-
# 저수준 마우스 훅 안전성 검증 도구(진단용). 대상 PC에 Python이 없을 수 있어 단독
# 실행 파일로 만든다. 진단 도구이므로 console=True — 콘솔 출력이 곧 산출물이다.
from PyInstaller.utils.hooks import collect_all

pynput_datas, pynput_binaries, pynput_hiddenimports = collect_all('pynput')

a = Analysis(
    ['scripts/verify_mouse_hook.py'],
    pathex=['.'],
    binaries=pynput_binaries,
    datas=pynput_datas,
    hiddenimports=pynput_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 이 도구는 pynput + 표준 라이브러리만 쓴다(Qt/numpy/mss 불필요)
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'numpy', 'mss', 'PySide6'],
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
    name='verify-mouse-hook',
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
