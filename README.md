# Clipper 🎬

A Python desktop application for loading, scrubbing, trimming, and exporting video clips with FFmpeg.

---

## Features

- **Video Playback** — Full playback with play/pause, stop, and frame-by-frame stepping
- **Custom Timeline Scrubber** — Click or drag to seek; visual tick marks with timecode labels
- **In/Out Points** — Drag the `I` and `O` handles on the timeline, or press `I`/`O` keys
- **Background Export** — FFmpeg runs in a QThread so the UI stays responsive
- **FFmpeg Log Viewer** — Full encoder output shown in-app
- **Drag & Drop** — Drop any video file onto the window to load it

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

## Project Structure

```
video_trimmer/
├── main.py                    # Entry point
├── requirements.txt
├── core/
│   ├── __init__.py
│   └── ffmpeg_worker.py       # FFmpeg probing, export presets, QThread worker
└── ui/
    ├── __init__.py
    ├── main_window.py         # Main application window
    ├── player_widget.py       # QMediaPlayer-based video player
    ├── timeline_widget.py     # Custom-drawn timeline with I/O handles
    ├── export_panel.py        # Right-side export configuration panel
    └── style.qss              # Dark industrial Qt stylesheet
```

---

## Notes

- The GIF export uses a two-pass palette method for high-quality output
- Seeking precision depends on the source file's keyframe interval; `-ss` before `-i` is used for fast seek
- ProRes 422 requires an FFmpeg build with `prores_ks` encoder support
