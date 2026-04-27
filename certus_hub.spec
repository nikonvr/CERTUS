# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ["CERTUS_HUB.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("certus.ico", "."),
        ("certus.svg", "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CERTUS_HUB",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="certus.ico",
)
