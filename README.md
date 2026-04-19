# Clipper

A Python desktop application for loading, scrubbing, trimming, and exporting video clips with FFmpeg.

---

## Features

- **Video Playback** — Full playback with play/pause, stop, and frame-by-frame stepping
- **Custom Timeline Scrubber** — Click or drag to seek; visual tick marks with timecode labels
- **In/Out Points** — Drag the `I` and `O` handles on the timeline, or press `I`/`O` keys
- **Background Export** — FFmpeg runs in a QThread so the UI stays responsive
- **FFmpeg Log Viewer** — Full encoder output shown in-app
- **Drag & Drop** — Drop a video or export log onto the window to load it; prompts before discarding adjusted trim points
- **Audio Mix Controls** — Per-stream volume and mute for multi-track files; preview the mixed output before export
- **Export Presets** — Built-in encoding presets plus a custom preset creator/manager (saved between sessions)
- **Split Output Path** — Separate folder and filename fields for the export destination
- **Export Logs** — Optionally save a `.txt` log alongside each clip; reload it later to restore all settings
- **Themes** — Built-in dark themes plus a custom theme editor

---

## Requirements

- **Python 3.10+**
- **FFmpeg** (with `ffprobe`) installed and on your `PATH`
- **PyQt6** (install via pip)

### Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add `ffmpeg.exe` to your PATH.

### Install Python dependencies

```bash
pip install -r requirements.txt
```

> On some Linux systems you may also need:
> ```bash
> sudo apt install python3-pyqt6 python3-pyqt6.qtmultimedia
> ```

---

## Running

```bash
python main.py
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `I` | Set In Point at current position |
| `O` | Set Out Point at current position |
| `,` | Step one frame back |
| `.` | Step one frame forward |
| `Ctrl+O` | Open video file |
| `Ctrl+Q` | Quit |

---

## Drag & Drop

Drop a **video file** onto the window to load it:
- If no video is loaded, it loads immediately.
- If a video is already loaded but trim points are at their defaults, it replaces automatically.
- If trim points have been adjusted, a confirmation prompt appears first.

Drop a **Clipper export log** (`.txt`) to restore a previous session — see [Export Logs](#export-logs) below.

---

## Audio Mix

When a file has multiple audio tracks, a per-stream control bar appears below the player:

- **Monitor** — select which track plays during preview
- **Mute** — exclude a track from the export
- **Volume slider** — scale a track's level (0–200%)
- **Preview Audio Mix** — renders the mixed audio to a temp file and plays it in sync with the video so you hear exactly what will be exported

---

## Export Presets

The export panel includes built-in presets (H.264, H.265, ProRes 422, GIF) as well as a custom preset system:

- **Save as Preset…** — saves the current encoding fields under a name of your choice
- **Delete** — removes a custom preset (built-in presets cannot be deleted)
- Custom presets are stored in system settings and persist between sessions

---

## Export Logs

Enable **Save log alongside clip** in the export panel to write a `.txt` file next to each exported clip. The log records:

- The source video path
- The in/out timecode range
- All encoding parameters (codec, bitrate, CRF, resolution, FPS, format, hardware acceleration)
- Per-track audio mix settings
- The exact FFmpeg command that was run

### Reloading a log

Open an export log via **File → Open Log…** or by dragging the `.txt` file onto the window. Clipper will:

1. Locate the original source video (or prompt you to browse for it if the path no longer exists)
2. Load the video and restore the in/out trim points
3. Restore all encoding parameters
4. Restore per-track audio mix settings
5. Pre-fill the output path from the original export

---

## Project Structure

```
clipper/
├── main.py                    # Entry point
├── requirements.txt
├── clipper.spec               # PyInstaller build spec
├── clipper_installer.iss      # Inno Setup installer script
├── build_installer.bat        # Local installer build helper
├── core/
│   ├── __init__.py
│   ├── constants.py           # App-wide constants (service name, etc.)
│   ├── ffmpeg_worker.py       # FFmpeg probing, export presets, QThread workers
│   └── log_parser.py          # Export log parser
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # Main application window
│   ├── player_widget.py       # QMediaPlayer-based video player + audio mix bar
│   ├── timeline_widget.py     # Custom-drawn timeline with I/O handles
│   ├── export_panel.py        # Right-side export configuration panel
│   ├── themes.py              # Theme definitions and manager
│   ├── theme_editor.py        # Custom theme editor dialog
│   └── style.qss              # Base Qt stylesheet
└── tests/
    ├── conftest.py
    ├── test_ffmpeg.py          # Export preset and probe_video tests
    ├── test_log_parser.py      # Export log parsing tests
    ├── test_themes.py          # Theme manager tests
    ├── test_theme_editor.py    # Theme editor dialog tests
    └── test_timeline.py        # Timeline widget tests
```

---

## Notes

- The GIF export uses a two-pass palette method for high-quality output
- Seeking precision depends on the source file's keyframe interval; `-ss` before `-i` is used for fast seek
- ProRes 422 requires an FFmpeg build with `prores_ks` encoder support
- The audio preview renders the full video's mixed audio once; scrubbing during preview stays in sync within ~200 ms
