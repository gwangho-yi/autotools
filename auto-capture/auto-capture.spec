# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/notify.wav', 'assets')],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='auto-capture',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='auto-capture',
)

app = BUNDLE(
    coll,
    name='auto-capture.app',
    icon='assets/icon.icns',
    bundle_identifier='com.autotools.auto-capture',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSUIElement': True,
        'NSScreenCaptureUsageDescription': '화면 변화 감지를 위해 화면 접근이 필요합니다.',
        'CFBundleDisplayName': 'auto-capture',
        'CFBundleVersion': '0.2.0',
        'CFBundleShortVersionString': '0.2.0',
    },
)
