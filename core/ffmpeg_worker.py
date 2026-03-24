"""
core/ffmpeg_worker.py
Handles all FFmpeg operations: probing, trimming, and platform-targeted encoding.
"""

import subprocess
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


# ---------------------------------------------------------------------------
# Export Presets
# ---------------------------------------------------------------------------

EXPORT_PRESETS = {
    "Discord (1080p 60 H.264)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "20000k",
        "audio_bitrate": "192k",
        "resolution": "1920x1080",
        "fps": "60",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p"],
    },
    "YouTube (1080p H.264)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "8000k",
        "audio_bitrate": "192k",
        "resolution": "1920x1080",
        "fps": "30",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p"],
    },
    "YouTube (4K H.264)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "35000k",
        "audio_bitrate": "320k",
        "resolution": "3840x2160",
        "fps": "60",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "5.1", "-pix_fmt", "yuv420p"],
    },
    "Instagram (Square 1080p)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "3500k",
        "audio_bitrate": "128k",
        "resolution": "1080x1080",
        "fps": "30",
        "format": "mp4",
        "extra": ["-profile:v", "baseline", "-level", "3.0", "-pix_fmt", "yuv420p"],
    },
    "Instagram Reels / TikTok (9:16)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "4000k",
        "audio_bitrate": "128k",
        "resolution": "1080x1920",
        "fps": "30",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p"],
    },
    "Twitter/X (1080p)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "5000k",
        "audio_bitrate": "128k",
        "resolution": "1920x1080",
        "fps": "40",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p"],
    },
    "Vimeo (1080p H.264)": {
        "vcodec": "libx264",
        "acodec": "aac",
        "video_bitrate": "10000k",
        "audio_bitrate": "320k",
        "resolution": "1920x1080",
        "fps": "24",
        "format": "mp4",
        "extra": ["-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p"],
    },
    "ProRes 422 (Archive)": {
        "vcodec": "prores_ks",
        "acodec": "pcm_s16le",
        "video_bitrate": None,
        "audio_bitrate": None,
        "resolution": None,
        "fps": None,
        "format": "mov",
        "extra": ["-profile:v", "2"],
    },
    "H.265 / HEVC (Efficient)": {
        "vcodec": "libx265",
        "acodec": "aac",
        "video_bitrate": "4000k",
        "audio_bitrate": "192k",
        "resolution": "1920x1080",
        "fps": "30",
        "format": "mp4",
        "extra": ["-tag:v", "hvc1", "-pix_fmt", "yuv420p"],
    },
    "GIF (Palette)": {
        "vcodec": "gif",
        "acodec": None,
        "video_bitrate": None,
        "audio_bitrate": None,
        "resolution": "640x360",
        "fps": "15",
        "format": "gif",
        "extra": [],
    },
    "Custom / Passthrough": {
        "vcodec": "copy",
        "acodec": "copy",
        "video_bitrate": None,
        "audio_bitrate": None,
        "resolution": None,
        "fps": None,
        "format": "mp4",
        "extra": [],
    },
}

# Hardware acceleration options: display name → ffmpeg flag value (empty = disabled)
HW_ACCEL_OPTIONS = {
    "None": "",
    "CUDA / NVDEC (NVIDIA)": "cuda",
    "D3D11VA (Windows)": "d3d11va",
    "DXVA2 (Windows)": "dxva2",
    "Intel QSV": "qsv",
    "VideoToolbox (macOS)": "videotoolbox",
}


# ---------------------------------------------------------------------------
# Video Metadata
# ---------------------------------------------------------------------------

@dataclass
class VideoInfo:
    path: str
    duration: float          # seconds
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str         # codec of the first audio stream
    size_bytes: int
    format_name: str
    audio_streams: list = field(default_factory=list)  # all audio stream dicts


def probe_video(path: str) -> VideoInfo:
    """Use ffprobe to extract video metadata including all audio streams."""
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe not found. Please install FFmpeg.")

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})

    # Parse FPS (can be "30/1" or "24000/1001")
    fps_raw = video_stream.get("r_frame_rate", "30/1")
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0

    # Collect all audio streams
    audio_streams = []
    for s in streams:
        if s.get("codec_type") != "audio":
            continue
        tags = s.get("tags", {})
        audio_streams.append({
            "stream_index": s.get("index", 0),      # index in the file
            "audio_index": len(audio_streams),       # 0-based audio-only index
            "codec_name": s.get("codec_name", "unknown"),
            "channels": s.get("channels", 2),
            "channel_layout": s.get("channel_layout", ""),
            "language": tags.get("language", ""),
            "title": tags.get("title", ""),
        })

    first_audio = audio_streams[0] if audio_streams else {}

    return VideoInfo(
        path=path,
        duration=float(fmt.get("duration", 0)),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=fps,
        video_codec=video_stream.get("codec_name", "unknown"),
        audio_codec=first_audio.get("codec_name", "none"),
        size_bytes=int(fmt.get("size", 0)),
        format_name=fmt.get("format_name", "unknown"),
        audio_streams=audio_streams,
    )


# ---------------------------------------------------------------------------
# Thumbnail Extraction
# ---------------------------------------------------------------------------

def extract_thumbnail(video_path: str, time_sec: float, output_path: str, width: int = 320) -> bool:
    """Extract a single frame as a JPEG thumbnail."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec),
        "-i", video_path,
        "-vframes", "1",
        "-vf", f"scale={width}:-1",
        "-q:v", "3",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=15)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bitrate_bps(bitrate_str: Optional[str]) -> int:
    """Parse a bitrate string like '192k', '5000k', '2m' into bits-per-second."""
    if not bitrate_str:
        return 0
    s = bitrate_str.lower().strip()
    try:
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        if s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        return int(s)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Export Worker (runs in background thread)
# ---------------------------------------------------------------------------

class ExportWorker(QThread):
    """
    Runs FFmpeg export in a background QThread.
    Emits progress (0-100), log lines, and completion/error signals.
    """
    progress = pyqtSignal(int)       # 0–100
    log_line = pyqtSignal(str)       # stderr line from ffmpeg
    finished = pyqtSignal(str)       # output path on success
    error = pyqtSignal(str)          # error message

    def __init__(
        self,
        input_path: str,
        output_path: str,
        start_sec: float,
        end_sec: float,
        preset_config: dict,
        target_size_mb: Optional[float] = None,
        hw_accel: str = "",
        audio_mix: Optional[list] = None,
        save_log: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.preset_config = preset_config
        self.target_size_mb = target_size_mb
        self.hw_accel = hw_accel
        self.audio_mix = audio_mix
        self.save_log = save_log
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None
        self._final_cmd: list = []  # stored for log file

    def cancel(self):
        self._cancelled = True
        if self._process:
            self._process.terminate()

    def run(self):
        try:
            preset = dict(self.preset_config)  # work on a copy
            duration = self.end_sec - self.start_sec

            # Target file size: compute video bitrate from desired size
            if self.target_size_mb is not None and preset.get("vcodec") not in ("copy", "gif"):
                target_bytes = self.target_size_mb * 1024 * 1024
                total_bps = (target_bytes * 8) / max(duration, 0.001)
                audio_bps = _parse_bitrate_bps(preset.get("audio_bitrate"))
                video_bps = max(100_000, total_bps - audio_bps)
                preset["video_bitrate"] = f"{int(video_bps / 1000)}k"
                self.log_line.emit(
                    f"[Target Size] {self.target_size_mb:.1f} MB over {duration:.1f}s "
                    f"→ video bitrate: {preset['video_bitrate']}"
                )

            # GIF special case
            if preset["vcodec"] == "gif":
                self._export_gif(preset, duration)
                return

            cmd = ["ffmpeg", "-y"]

            # Hardware acceleration (decode)
            if self.hw_accel:
                cmd += ["-hwaccel", self.hw_accel]

            # Input
            cmd += [
                "-ss", f"{self.start_sec:.6f}",
                "-i", self.input_path,
                "-t", f"{duration:.6f}",
            ]

            # --- Video codec ---
            if preset["vcodec"] == "copy":
                cmd += ["-c:v", "copy"]
            else:
                cmd += ["-c:v", preset["vcodec"]]
                crf = preset.get("crf")
                if crf and self.target_size_mb is None:
                    # CRF mode: constant quality, variable bitrate.
                    # Only active when target size is not in use.
                    cmd += ["-crf", str(crf)]
                elif preset.get("video_bitrate"):
                    cmd += ["-b:v", preset["video_bitrate"]]
                if preset.get("fps"):
                    cmd += ["-r", preset["fps"]]

            # --- Build video filter string ---
            vf_str = None
            if preset.get("resolution") and preset["vcodec"] != "copy":
                w, h = preset["resolution"].split("x")
                vf_str = (
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
                )

            # --- Build audio args ---
            # audio_codec_args: codec/bitrate flags
            # audio_filter_str: filter_complex audio fragment (None if not needed)
            # audio_map_args: explicit -map args for audio (empty if using default mapping)
            audio_codec_args = []
            audio_filter_str = None
            audio_map_args = []

            if self.audio_mix is None:
                # Default: use preset audio settings, no explicit mapping
                if preset["acodec"] is None:
                    audio_codec_args += ["-an"]
                elif preset["acodec"] == "copy":
                    audio_codec_args += ["-c:a", "copy"]
                else:
                    audio_codec_args += ["-c:a", preset["acodec"]]
                    if preset.get("audio_bitrate"):
                        audio_codec_args += ["-b:a", preset["audio_bitrate"]]
            else:
                active = [s for s in self.audio_mix if not s.get("mute", False)]
                if not active:
                    audio_codec_args += ["-an"]
                else:
                    needs_filter = (
                        len(active) > 1 or
                        abs(active[0].get("volume", 1.0) - 1.0) > 0.01
                    )
                    if needs_filter:
                        # Build audio filter graph
                        parts = []
                        for i, s in enumerate(active):
                            vol = s.get("volume", 1.0)
                            parts.append(f"[0:a:{s['audio_index']}]volume={vol:.3f}[av{i}]")
                        if len(active) == 1:
                            audio_filter_str = (
                                f"[0:a:{active[0]['audio_index']}]"
                                f"volume={active[0]['volume']:.3f}[aout]"
                            )
                        else:
                            mix_in = "".join(f"[av{i}]" for i in range(len(active)))
                            audio_filter_str = (
                                ";".join(parts) +
                                f";{mix_in}amix=inputs={len(active)}:normalize=0[aout]"
                            )
                        audio_map_args = ["-map", "[aout]"]
                    else:
                        # Single stream, unity volume: simple explicit map
                        audio_map_args = ["-map", f"0:a:{active[0]['audio_index']}"]

                    # Audio codec for active streams
                    if preset["acodec"] not in (None, "copy"):
                        audio_codec_args += ["-c:a", preset["acodec"]]
                        if preset.get("audio_bitrate"):
                            audio_codec_args += ["-b:a", preset["audio_bitrate"]]
                    elif preset["acodec"] == "copy":
                        audio_codec_args += ["-c:a", "copy"]

            # --- Combine filters and mapping ---
            explicit_map = bool(audio_map_args or audio_filter_str)

            if audio_filter_str and vf_str:
                # Combine video and audio in one filter_complex
                fc = f"[0:v]{vf_str}[vout];{audio_filter_str}"
                cmd += ["-filter_complex", fc, "-map", "[vout]"] + audio_map_args
            elif audio_filter_str:
                cmd += ["-filter_complex", audio_filter_str, "-map", "0:v"] + audio_map_args
            elif vf_str:
                cmd += ["-vf", vf_str]
                if explicit_map:
                    cmd += ["-map", "0:v"] + audio_map_args
            elif explicit_map:
                cmd += ["-map", "0:v"] + audio_map_args

            cmd += audio_codec_args
            cmd += preset.get("extra", [])
            cmd += ["-progress", "pipe:1", self.output_path]

            self._final_cmd = cmd
            self.log_line.emit(f"$ {' '.join(cmd)}\n")

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Read stderr for log
            import threading
            def read_stderr():
                for line in self._process.stderr:
                    self.log_line.emit(line.rstrip())

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Parse progress from stdout
            current_time = 0.0
            for line in self._process.stdout:
                line = line.strip()
                if line.startswith("out_time_ms="):
                    try:
                        ms = int(line.split("=")[1])
                        current_time = ms / 1_000_000
                        pct = min(99, int((current_time / duration) * 100))
                        self.progress.emit(pct)
                    except Exception:
                        pass

            self._process.wait()
            stderr_thread.join(timeout=2)

            if self._cancelled:
                self.error.emit("Export cancelled.")
                if os.path.exists(self.output_path):
                    os.remove(self.output_path)
                return

            if self._process.returncode != 0:
                self.error.emit("FFmpeg exited with an error. Check the log for details.")
                return

            self.progress.emit(100)

            if self.save_log:
                self._write_log_file(preset, duration)

            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))

    def _write_log_file(self, preset: dict, duration: float):
        """Write encoding parameters to a .txt file alongside the output."""
        log_path = os.path.splitext(self.output_path)[0] + ".txt"
        try:
            def fmt_tc(sec):
                h, rem = divmod(int(sec), 3600)
                m, s = divmod(rem, 60)
                ms = int((sec % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

            lines = [
                "VideoForge Export Log",
                "=" * 40,
                f"Date:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Input:    {self.input_path}",
                f"Output:   {self.output_path}",
                f"Start:    {fmt_tc(self.start_sec)}",
                f"End:      {fmt_tc(self.end_sec)}",
                f"Duration: {fmt_tc(duration)}",
                "",
                "Encoding Parameters:",
                f"  V-Codec:    {preset.get('vcodec', '')}",
                f"  CRF:        {preset.get('crf') or '(not set)'}",
                f"  V-Bitrate:  {preset.get('video_bitrate') or '(auto)'}",
                f"  A-Codec:    {preset.get('acodec', '')}",
                f"  A-Bitrate:  {preset.get('audio_bitrate') or '(auto)'}",
                f"  Resolution: {preset.get('resolution') or '(source)'}",
                f"  FPS:        {preset.get('fps') or '(source)'}",
                f"  Format:     {preset.get('format', '')}",
                f"  HW Accel:   {self.hw_accel or 'none'}",
                f"  Extra:      {' '.join(preset.get('extra', []))}",
            ]

            if self.target_size_mb is not None:
                lines.append("")
                lines.append(f"Target Size: {self.target_size_mb:.1f} MB"
                              f" (computed bitrate: {preset.get('video_bitrate', '?')})")

            if self.audio_mix:
                lines.append("")
                lines.append("Audio Mix:")
                for s in self.audio_mix:
                    vol_pct = int(s.get("volume", 1.0) * 100)
                    muted = "muted" if s.get("mute") else f"volume {vol_pct}%"
                    lines.append(f"  Track {s['audio_index'] + 1}: {muted}")

            lines += [
                "",
                "FFmpeg Command:",
                "  " + " ".join(self._final_cmd),
            ]

            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            self.log_line.emit(f"[Log] Could not write log file: {e}")

    def _export_gif(self, preset: dict, duration: float):
        """Two-pass GIF export with palette generation."""
        import tempfile
        palette_path = tempfile.mktemp(suffix=".png")
        w, h = (preset.get("resolution") or "640x360").split("x")
        fps = preset.get("fps") or "15"

        scale_filter = f"fps={fps},scale={w}:{h}:flags=lanczos"

        # Pass 1: generate palette
        cmd1 = [
            "ffmpeg", "-y",
            "-ss", f"{self.start_sec:.6f}",
            "-i", self.input_path,
            "-t", f"{duration:.6f}",
            "-vf", f"{scale_filter},palettegen",
            palette_path
        ]
        self.log_line.emit("GIF Pass 1: Generating palette...")
        r1 = subprocess.run(cmd1, capture_output=True, text=True)
        if r1.returncode != 0:
            self.error.emit(f"GIF palette generation failed: {r1.stderr}")
            return

        self.progress.emit(40)

        # Pass 2: encode with palette
        cmd2 = [
            "ffmpeg", "-y",
            "-ss", f"{self.start_sec:.6f}",
            "-i", self.input_path,
            "-i", palette_path,
            "-t", f"{duration:.6f}",
            "-lavfi", f"{scale_filter} [x]; [x][1:v] paletteuse",
            self.output_path
        ]
        self.log_line.emit("GIF Pass 2: Encoding with palette...")
        r2 = subprocess.run(cmd2, capture_output=True, text=True)

        if os.path.exists(palette_path):
            os.remove(palette_path)

        if r2.returncode != 0:
            self.error.emit(f"GIF encoding failed: {r2.stderr}")
            return

        self.progress.emit(100)
        self.finished.emit(self.output_path)
