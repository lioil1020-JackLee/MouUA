# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# 動態檢查圖示檔案
# Windows: lioil.ico，macOS: lioil.icns
datas_list = []

# 根據運行平台選擇圖示
if sys.platform == 'darwin':  # macOS
    if os.path.exists('lioil.icns'):
        datas_list.append(('lioil.icns', '.'))
else:  # Windows
    if os.path.exists('lioil.ico'):
        datas_list.append(('lioil.ico', '.'))

# 設定 EXE 圖示參數
icon_param = []
if sys.platform == 'darwin':
    if os.path.exists('lioil.icns'):
        icon_param = ['lioil.icns']
else:
    if os.path.exists('lioil.ico'):
        icon_param = ['lioil.ico']

a = Analysis(
    ['ModUA.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ModUA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_param,
)
