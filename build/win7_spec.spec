# -*- mode: python ; coding: utf-8 -*-

import os, sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

pyside2_dir = os.path.join(sys.prefix, "Lib", "site-packages", "PySide2", "plugins")

datas = collect_data_files("PySide2")
pyside2_plugins = [
    (os.path.join(pyside2_dir, "platforms"), "PySide2/plugins/platforms"),
]

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=datas + pyside2_plugins,
    hiddenimports=[
        "PySide2.QtCore",
        "PySide2.QtGui",
        "PySide2.QtWidgets",
        "shiboken2"
    ],
    hookspath=[],
    hooksconfig={},
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Sfera36',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True
)
