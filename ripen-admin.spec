# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

datas = [('src/ripen', 'ripen')]
datas += copy_metadata('fastmcp')
datas += copy_metadata('ripen')


a = Analysis(
    ['C:\\Users\\saiha\\My_Service\\programing\\MCP\\Ripen\\Ripen-free\\ripen_launcher_admin.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['ripen.cli.init', 'ripen.cli.admin_cli', 'ripen.cli.shortcut'],
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
    name='ripen-admin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\saiha\\My_Service\\programing\\MCP\\Ripen\\Ripen-free\\logo.ico'],
)
