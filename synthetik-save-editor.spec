# -*- mode: python ; coding: utf-8 -*-
# Windowed launcher. PyInstaller packs the Python interpreter with this program.
# Build it yourself with build_exe.bat if you do not want a prebuilt download.

a = Analysis(
    ['editor.pyw'],
    pathex=[],
    binaries=[],
    datas=[('research/gamedata', 'research/gamedata')],
    hiddenimports=['gui', 'game_icons'],
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
    name='synthetik-save-editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
