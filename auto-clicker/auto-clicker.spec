# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/notify.wav', 'assets'),
        ('assets/icon.icns', 'assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'pynput.mouse._darwin',
        'pynput.keyboard._darwin',
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
    name='auto-clicker',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='auto-clicker',
)

app = BUNDLE(
    coll,
    name='auto-clicker.app',
    icon='assets/icon.icns',
    bundle_identifier='com.autotools.auto-clicker',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleDisplayName': 'auto-clicker',
        'CFBundleVersion': '0.2.1',
        'CFBundleShortVersionString': '0.2.1',
    },
)
