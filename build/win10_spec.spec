# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../sfera36_terminal/main.py'],
    pathex=['..'],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtCore'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Sfera36',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    version='version_info.txt',
    manifest='app.manifest'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sfera36_win10'
)
