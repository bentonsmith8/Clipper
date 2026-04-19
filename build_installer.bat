@echo off
setlocal

echo === Clipper installer build ===
echo.

REM ── 1. Check ffmpeg binaries are present ──────────────────────────────────
if not exist ffmpeg.exe (
    echo ERROR: ffmpeg.exe not found in project root.
    echo Download a static Windows build from https://www.gyan.dev/ffmpeg/builds/
    echo and copy ffmpeg.exe, ffprobe.exe, and ffplay.exe here before running this script.
    exit /b 1
)
if not exist ffprobe.exe (
    echo ERROR: ffprobe.exe not found.
    exit /b 1
)
if not exist ffplay.exe (
    echo WARNING: ffplay.exe not found. Continuing without it.
)

REM ── 2. Build with PyInstaller ─────────────────────────────────────────────
echo [1/2] Building with PyInstaller...
pyinstaller clipper.spec --clean --noconfirm
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

REM ── 3. Compile Inno Setup installer ──────────────────────────────────────
echo [2/2] Compiling Inno Setup installer...
where iscc >nul 2>&1
if errorlevel 1 (
    echo ERROR: iscc not found on PATH.
    echo Install Inno Setup from https://jrsoftware.org/isinfo.php
    echo then re-run this script, or open clipper_installer.iss in the Inno Setup IDE.
    exit /b 1
)
iscc clipper_installer.iss
if errorlevel 1 (
    echo Inno Setup compilation failed.
    exit /b 1
)

echo.
echo Done! Installer is in installer_output\ClipperInstaller-v1.0.0.exe
endlocal
