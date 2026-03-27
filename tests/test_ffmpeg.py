"""
Regression tests for core/ffmpeg_worker.py.

Covers:
- Every export preset has the required fields with sensible values.
- _parse_bitrate_bps handles all valid formats and edge cases.
- probe_video correctly parses ffprobe JSON output (subprocess mocked).
- VideoInfo is a proper dataclass with all expected fields.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from core.ffmpeg_worker import (
    EXPORT_PRESETS,
    VideoInfo,
    _parse_bitrate_bps,
    probe_video,
)

# Required keys in every preset dict.
PRESET_REQUIRED_KEYS = {"vcodec", "acodec", "video_bitrate", "audio_bitrate",
                        "resolution", "fps", "format", "extra"}

VALID_FORMATS = {"mp4", "mov", "gif"}
VALID_VCODECS = {"libx264", "libx265", "prores_ks", "gif", "copy"}


# ──────────────────────────────────────────────────────────────────────────────
# Export preset structure
# ──────────────────────────────────────────────────────────────────────────────

def test_at_least_one_preset_defined():
    assert len(EXPORT_PRESETS) >= 1


@pytest.mark.parametrize("preset_name", list(EXPORT_PRESETS.keys()))
def test_preset_has_all_required_keys(preset_name):
    missing = PRESET_REQUIRED_KEYS - set(EXPORT_PRESETS[preset_name].keys())
    assert not missing, f"Preset '{preset_name}' is missing keys: {missing}"


@pytest.mark.parametrize("preset_name", list(EXPORT_PRESETS.keys()))
def test_preset_format_is_valid(preset_name):
    fmt = EXPORT_PRESETS[preset_name]["format"]
    assert fmt in VALID_FORMATS, (
        f"Preset '{preset_name}' has unknown format '{fmt}'"
    )


@pytest.mark.parametrize("preset_name", list(EXPORT_PRESETS.keys()))
def test_preset_extra_is_a_list(preset_name):
    assert isinstance(EXPORT_PRESETS[preset_name]["extra"], list), (
        f"Preset '{preset_name}'.extra must be a list"
    )


@pytest.mark.parametrize("preset_name", list(EXPORT_PRESETS.keys()))
def test_preset_extra_has_even_length(preset_name):
    """ffmpeg flags come in -flag value pairs, so extra must be even-length (or empty)."""
    extra = EXPORT_PRESETS[preset_name]["extra"]
    assert len(extra) % 2 == 0, (
        f"Preset '{preset_name}'.extra has odd length {len(extra)} — "
        "flags and values should pair up"
    )


def test_no_duplicate_preset_names():
    assert len(EXPORT_PRESETS) == len(set(EXPORT_PRESETS.keys()))


# ──────────────────────────────────────────────────────────────────────────────
# _parse_bitrate_bps
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bitrate_str, expected_bps", [
    ("192k",    192_000),
    ("5000k",   5_000_000),
    ("320k",    320_000),
    ("2m",      2_000_000),
    ("1.5m",    1_500_000),
    ("128000",  128_000),
    ("0",       0),
])
def test_parse_bitrate_bps_valid(bitrate_str, expected_bps):
    assert _parse_bitrate_bps(bitrate_str) == expected_bps


@pytest.mark.parametrize("invalid", [None, "", "abc", "k", "m"])
def test_parse_bitrate_bps_invalid_returns_zero(invalid):
    assert _parse_bitrate_bps(invalid) == 0


# ──────────────────────────────────────────────────────────────────────────────
# VideoInfo dataclass
# ──────────────────────────────────────────────────────────────────────────────

def test_videoinfo_fields_exist():
    info = VideoInfo(
        path="/tmp/test.mp4",
        duration=60.0,
        width=1920,
        height=1080,
        fps=29.97,
        video_codec="h264",
        audio_codec="aac",
        size_bytes=50_000_000,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    )
    assert info.path == "/tmp/test.mp4"
    assert info.duration == 60.0
    assert info.width == 1920
    assert info.height == 1080
    assert abs(info.fps - 29.97) < 0.001
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.size_bytes == 50_000_000
    assert info.audio_streams == []  # default_factory


# ──────────────────────────────────────────────────────────────────────────────
# probe_video  (subprocess mocked — no real ffprobe needed)
# ──────────────────────────────────────────────────────────────────────────────

def _make_ffprobe_result(streams, format_dict):
    """Build a mock subprocess.run result with ffprobe-shaped JSON output."""
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = json.dumps({"streams": streams, "format": format_dict})
    mock.stderr = ""
    return mock


@pytest.fixture
def simple_ffprobe_data():
    streams = [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "index": 1,
            "channels": 2,
            "channel_layout": "stereo",
            "tags": {"language": "eng"},
        },
    ]
    fmt = {"duration": "120.5", "size": "50000000", "format_name": "mov,mp4"}
    return streams, fmt


def test_probe_video_basic_fields(simple_ffprobe_data):
    streams, fmt = simple_ffprobe_data
    mock_result = _make_ffprobe_result(streams, fmt)

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        info = probe_video("/fake/video.mp4")

    assert info.path == "/fake/video.mp4"
    assert info.width == 1920
    assert info.height == 1080
    assert info.fps == 30.0
    assert info.duration == pytest.approx(120.5)
    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert info.size_bytes == 50_000_000
    assert info.format_name == "mov,mp4"


def test_probe_video_audio_streams_collected(simple_ffprobe_data):
    streams, fmt = simple_ffprobe_data
    mock_result = _make_ffprobe_result(streams, fmt)

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        info = probe_video("/fake/video.mp4")

    assert len(info.audio_streams) == 1
    assert info.audio_streams[0]["codec_name"] == "aac"
    assert info.audio_streams[0]["channels"] == 2
    assert info.audio_streams[0]["language"] == "eng"
    assert info.audio_streams[0]["audio_index"] == 0


def test_probe_video_fractional_fps():
    streams = [{"codec_type": "video", "codec_name": "h264",
                "width": 1280, "height": 720, "r_frame_rate": "24000/1001"}]
    fmt = {"duration": "10.0", "size": "1000000", "format_name": "mp4"}
    mock_result = _make_ffprobe_result(streams, fmt)

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        info = probe_video("/fake/video.mp4")

    assert info.fps == pytest.approx(23.976, abs=0.001)


def test_probe_video_no_audio_stream():
    streams = [{"codec_type": "video", "codec_name": "hevc",
                "width": 3840, "height": 2160, "r_frame_rate": "60/1"}]
    fmt = {"duration": "5.0", "size": "200000", "format_name": "mp4"}
    mock_result = _make_ffprobe_result(streams, fmt)

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        info = probe_video("/fake/video.mp4")

    assert info.audio_codec == "none"
    assert info.audio_streams == []


def test_probe_video_multiple_audio_streams():
    streams = [
        {"codec_type": "video", "codec_name": "h264",
         "width": 1920, "height": 1080, "r_frame_rate": "25/1"},
        {"codec_type": "audio", "codec_name": "aac", "index": 1,
         "channels": 2, "channel_layout": "stereo", "tags": {"language": "eng"}},
        {"codec_type": "audio", "codec_name": "ac3", "index": 2,
         "channels": 6, "channel_layout": "5.1", "tags": {"language": "fra"}},
    ]
    fmt = {"duration": "90.0", "size": "800000000", "format_name": "mkv"}
    mock_result = _make_ffprobe_result(streams, fmt)

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        info = probe_video("/fake/video.mkv")

    assert len(info.audio_streams) == 2
    assert info.audio_streams[0]["codec_name"] == "aac"
    assert info.audio_streams[1]["codec_name"] == "ac3"
    assert info.audio_streams[0]["audio_index"] == 0
    assert info.audio_streams[1]["audio_index"] == 1


def test_probe_video_raises_when_ffprobe_missing():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffprobe not found"):
            probe_video("/fake/video.mp4")


def test_probe_video_raises_on_nonzero_returncode():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "No such file"

    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="ffprobe failed"):
            probe_video("/fake/missing.mp4")
