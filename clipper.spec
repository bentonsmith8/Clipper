# clipper.spec
# Build with: pyinstaller clipper.spec
#
# Prerequisites:
#   pip install pyinstaller
#
# FFmpeg: either ensure ffmpeg/ffprobe are on the end-user's PATH,
# or drop ffmpeg.exe + ffprobe.exe into this directory and uncomment
# the BUNDLE_FFMPEG lines below.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

BUNDLE_FFMPEG = True  # set True if bundling ffmpeg.exe/ffprobe.exe here

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------

datas = [
    ('ui/style_template.qss', 'ui'),
]

if BUNDLE_FFMPEG:
    datas += [
        ('ffmpeg.exe',  '.'),
        ('ffprobe.exe', '.'),
        ('ffplay.exe',  '.'),
    ]

# Collect Qt6 plugins (codecs, multimedia backends, platform plugins, etc.)
qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')
datas    += qt_datas

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_binaries,
    datas=datas,
    hiddenimports=qt_hiddenimports + [
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'IPython',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# Executable
# ---------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,      # binaries go into COLLECT, not the exe
    name='Clipper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                   # compress with UPX if available
    console=False,              # no console window
    icon=None,                  # replace with 'clipper.ico' if you have one
)

# ---------------------------------------------------------------------------
# Collect (folder distribution)
# ---------------------------------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Clipper',
)

# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
# Output: dist/Clipper/Clipper.exe  (+ supporting files in dist/Clipper/)
#
# To share: zip dist/Clipper/ and distribute.
#
# If end users don't have FFmpeg:
#   1. Download a static Windows build from https://ffmpeg.org/download.html
#   2. Copy ffmpeg.exe, ffprobe.exe, ffplay.exe into this project directory
#   3. Set BUNDLE_FFMPEG = True above and rebuild
#
# To make a single-file .exe instead (slower cold start, same size):
#   Change exclude_binaries=True → False, add a.binaries and a.datas to EXE,
#   and remove the COLLECT block.
