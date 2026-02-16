# -*- mode: python ; coding: utf-8 -*-
import os
import sys

datas_list = [
    ('ui', 'ui'),
    ('images', 'images'),
    ('core', 'core'),
    ('certs', 'certs')
]

app_name = 'ModUA-macos-onefile' if sys.platform == 'darwin' else 'ModUA-onefile'

icon_param = None
if sys.platform == 'darwin':
    if os.path.exists('lioil.icns'):
        datas_list.insert(0, ('lioil.icns', '.'))
        icon_param = 'lioil.icns'
else:
    if os.path.exists('lioil.ico'):
        datas_list.insert(0, ('lioil.ico', '.'))
        icon_param = 'lioil.ico'

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
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    icon=icon_param,
    # ✅ macOS 特定：使用臨時代碼簽名（開發用）
    # 註：移除 target_arch='universal2' 以避免庫兼容性問題
    # 在 ARM64 Mac 上編譯產生 ARM64 版本，在 Intel Mac 上編譯產生 x86_64 版本
    # 如果需要跨架構支持，需要在支持該架構的機器上分別編譯
    codesign_identity='-' if sys.platform == 'darwin' else None,
)

# ✅ macOS 特定的打包處理 - 創建 .app 束文件結構
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name=app_name + '.app',
        icon=icon_param,
        bundle_identifier='com.modua.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',  # ✅ 支持 Retina 高 DPI
            'NSRequiresIPhoneOSSDK': False,
            # ✅ 允許應用在受保護的環境中運行
            'NSLocalNetworkUsageDescription': 'ModUA needs access to local network devices for Modbus communication',
            'NSBonjourServices': ['_modbus._tcp', '_opcua._tcp'],
        },
    )
else:
    # Windows: 使用 COLLECT 打包
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=app_name,
    )