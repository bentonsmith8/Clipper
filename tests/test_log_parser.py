"""
Tests for core/log_parser.py.

Covers:
- Happy-path parsing of a complete export log.
- Placeholder values (auto/source/not set/none) converted to empty strings.
- Timecode-to-seconds conversion (HH:MM:SS.mmm).
- Audio mix section: muted tracks and percentage-volume tracks.
- Log with no audio mix section.
- Multiple audio tracks.
- Invalid / non-log files raise ValueError.
"""

import textwrap
import pytest

from core.log_parser import parse_export_log, _tc_to_seconds


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _write_log(tmp_path, content: str) -> str:
    """Write *content* to a temp .txt file and return its path."""
    p = tmp_path / "export.txt"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


FULL_LOG = """\
    Clipper Export Log
    ========================================
    Date:     2024-03-10 14:22:00
    Input:    /videos/source.mp4
    Output:   /clips/out.mp4
    Start:    00:00:05.250
    End:      00:01:30.500
    Duration: 00:01:25.250

    Encoding Parameters:
      V-Codec:    libx264
      CRF:        23
      V-Bitrate:  (auto)
      A-Codec:    aac
      A-Bitrate:  128k
      Resolution: 1920x1080
      FPS:        (source)
      Format:     mp4
      HW Accel:   cuda
      Extra:      -movflags +faststart

    Audio Mix:
      Track 1: volume 100%
      Track 2: muted

    FFmpeg Command:
      ffmpeg -i /videos/source.mp4 /clips/out.mp4
"""

MINIMAL_LOG = """\
    Clipper Export Log
    ========================================
    Date:     2024-01-01 00:00:00
    Input:    /a/b.mp4
    Output:   /c/d.mp4
    Start:    00:00:00.000
    End:      00:00:10.000
    Duration: 00:00:10.000

    Encoding Parameters:
      V-Codec:    copy
      CRF:        (not set)
      V-Bitrate:  (auto)
      A-Codec:    copy
      A-Bitrate:  (auto)
      Resolution: (source)
      FPS:        (source)
      Format:     mp4
      HW Accel:   none
      Extra:

    FFmpeg Command:
      ffmpeg -i /a/b.mp4 /c/d.mp4
"""


# ──────────────────────────────────────────────────────────────────────────────
# _tc_to_seconds
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tc, expected", [
    ("00:00:00.000",  0.0),
    ("00:00:05.000",  5.0),
    ("00:01:00.000",  60.0),
    ("01:00:00.000",  3600.0),
    ("00:01:30.500",  90.5),
    ("01:23:45.678",  5025.678),
])
def test_tc_to_seconds(tc, expected):
    assert _tc_to_seconds(tc) == pytest.approx(expected, abs=0.001)


# ──────────────────────────────────────────────────────────────────────────────
# Happy-path parsing
# ──────────────────────────────────────────────────────────────────────────────

def test_parse_input_output_paths(tmp_path):
    log = parse_export_log(_write_log(tmp_path, FULL_LOG))
    assert log["input_path"]  == "/videos/source.mp4"
    assert log["output_path"] == "/clips/out.mp4"


def test_parse_start_end_seconds(tmp_path):
    log = parse_export_log(_write_log(tmp_path, FULL_LOG))
    assert log["start_sec"] == pytest.approx(5.25,  abs=0.001)
    assert log["end_sec"]   == pytest.approx(90.5,  abs=0.001)


def test_parse_encoding_set_values(tmp_path):
    enc = parse_export_log(_write_log(tmp_path, FULL_LOG))["encoding"]
    assert enc["vcodec"]      == "libx264"
    assert enc["crf"]         == "23"
    assert enc["acodec"]      == "aac"
    assert enc["audio_bitrate"] == "128k"
    assert enc["resolution"]  == "1920x1080"
    assert enc["format"]      == "mp4"
    assert enc["hw_accel"]    == "cuda"
    assert enc["extra"]       == "-movflags +faststart"


def test_parse_placeholders_become_empty_string(tmp_path):
    enc = parse_export_log(_write_log(tmp_path, FULL_LOG))["encoding"]
    # (auto) and (source) in FULL_LOG
    assert enc["video_bitrate"] == ""
    assert enc["fps"]           == ""


# ──────────────────────────────────────────────────────────────────────────────
# Placeholder normalisation
# ──────────────────────────────────────────────────────────────────────────────

def test_all_placeholders_normalised(tmp_path):
    enc = parse_export_log(_write_log(tmp_path, MINIMAL_LOG))["encoding"]
    assert enc["crf"]           == ""   # (not set)
    assert enc["video_bitrate"] == ""   # (auto)
    assert enc["audio_bitrate"] == ""   # (auto)
    assert enc["resolution"]    == ""   # (source)
    assert enc["fps"]           == ""   # (source)
    assert enc["hw_accel"]      == ""   # none
    assert enc["extra"]         == ""   # blank


# ──────────────────────────────────────────────────────────────────────────────
# Audio mix
# ──────────────────────────────────────────────────────────────────────────────

def test_audio_mix_track_count(tmp_path):
    log = parse_export_log(_write_log(tmp_path, FULL_LOG))
    assert len(log["audio_mix"]) == 2


def test_audio_mix_volume_track(tmp_path):
    mix = parse_export_log(_write_log(tmp_path, FULL_LOG))["audio_mix"]
    track1 = mix[0]
    assert track1["audio_index"] == 0
    assert track1["muted"] is False
    assert track1["volume"] == pytest.approx(1.0)


def test_audio_mix_muted_track(tmp_path):
    mix = parse_export_log(_write_log(tmp_path, FULL_LOG))["audio_mix"]
    track2 = mix[1]
    assert track2["audio_index"] == 1
    assert track2["muted"] is True


def test_audio_mix_partial_volume(tmp_path):
    log_text = FULL_LOG.replace("Track 1: volume 100%", "Track 1: volume 75%")
    mix = parse_export_log(_write_log(tmp_path, log_text))["audio_mix"]
    assert mix[0]["volume"] == pytest.approx(0.75)


def test_no_audio_mix_section(tmp_path):
    log = parse_export_log(_write_log(tmp_path, MINIMAL_LOG))
    assert log["audio_mix"] == []


def test_multiple_audio_tracks(tmp_path):
    log_text = FULL_LOG.replace(
        "Audio Mix:\n      Track 1: volume 100%\n      Track 2: muted",
        "Audio Mix:\n      Track 1: volume 80%\n      Track 2: muted\n      Track 3: volume 50%",
    )
    mix = parse_export_log(_write_log(tmp_path, log_text))["audio_mix"]
    assert len(mix) == 3
    assert mix[0] == {"audio_index": 0, "muted": False, "volume": pytest.approx(0.80)}
    assert mix[1] == {"audio_index": 1, "muted": True,  "volume": pytest.approx(1.0)}
    assert mix[2] == {"audio_index": 2, "muted": False, "volume": pytest.approx(0.50)}


# ──────────────────────────────────────────────────────────────────────────────
# Error cases
# ──────────────────────────────────────────────────────────────────────────────

def test_invalid_file_raises_value_error(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("This is not a Clipper log.\nJust some random text.\n")
    with pytest.raises(ValueError, match="Not a Clipper export log"):
        parse_export_log(str(bad))


def test_empty_file_raises_value_error(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    with pytest.raises(ValueError):
        parse_export_log(str(empty))


def test_missing_file_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        parse_export_log(str(tmp_path / "nonexistent.txt"))
