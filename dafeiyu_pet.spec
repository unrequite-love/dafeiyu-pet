# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：python -m PyInstaller --noconfirm dafeiyu_pet.spec"""
from PyInstaller.utils.hooks import collect_all

datas = [("sprites", "sprites")]
binaries = []
hiddenimports = []
for _pkg in ("psutil", "requests", "pynvml"):
    _tmp = collect_all(_pkg)
    datas += _tmp[0]
    binaries += _tmp[1]
    hiddenimports += _tmp[2]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="dafeiyu-pet",
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
    icon=["icon.ico"],
)
