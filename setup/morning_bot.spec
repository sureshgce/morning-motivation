# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Morning Momentum Bot.

Produces a single-folder distribution with morning_bot.exe.
The exe is windowless (no console) — runs silently in the system tray.

Build command:
    pyinstaller morning_bot.spec

Output:
    dist/morning_bot/morning_bot.exe
"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['morning_bot.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pystray._win32',      # Windows tray backend
        'PIL._tkinter_finder', # Pillow + tkinter bridge
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'scipy', 'pandas',
        'pytest', 'unittest', 'doctest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='morning_bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # <-- windowless (no console popup)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # TODO: add .ico file if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='morning_bot',
)
