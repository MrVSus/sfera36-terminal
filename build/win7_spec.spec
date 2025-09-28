# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Ресурсы для PySide2
datas = collect_data_files("PySide2")

# Импорты для PySide2
hiddenimports = [
    "PySide2.QtCore",
    "PySide2.QtGui",
    "PySide2.QtWidgets",
    "shiboken2"
]

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    upx=False,  # отключаем UPX
    console=False,
    version='version_info.txt',  
    manifest='build/app.manifest',     
    win_private_assemblies=True, 
)

