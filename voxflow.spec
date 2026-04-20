# PyInstaller spec for VoxFlow.
# Builds a single folder under ./dist/voxflow containing the entry binary + deps.
# Run with:  pyinstaller voxflow.spec --clean --noconfirm

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# faster-whisper + ctranslate2 carry runtime assets (model metadata, tokenizer)
for pkg in ("faster_whisper", "ctranslate2", "tokenizers"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# pystray backend imports are dynamic
hiddenimports += [
    "pystray._win32", "pystray._darwin", "pystray._xorg",
    "PIL.ImageDraw", "PIL.Image",
    "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
    "sounddevice",
]


a = Analysis(
    ["voxflow/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name="voxflow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="voxflow",
)
