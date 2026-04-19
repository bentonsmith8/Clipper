"""
core/log_parser.py
Parses Clipper export log files (.txt) back into structured dicts.
"""

import re


def _tc_to_seconds(tc: str) -> float:
    """Convert HH:MM:SS.mmm timecode string to float seconds."""
    parts = tc.strip().split(":")
    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


_PLACEHOLDERS = {"(not set)", "(auto)", "(source)", "none"}

_ENCODING_KEYS = {
    "V-Codec":    "vcodec",
    "A-Codec":    "acodec",
    "CRF":        "crf",
    "V-Bitrate":  "video_bitrate",
    "A-Bitrate":  "audio_bitrate",
    "Resolution": "resolution",
    "FPS":        "fps",
    "Format":     "format",
    "HW Accel":   "hw_accel",
    "Extra":      "extra",
}


def parse_export_log(path: str) -> dict:
    """
    Parse a Clipper export log and return:
      input_path  : str
      output_path : str
      start_sec   : float
      end_sec     : float
      encoding    : dict with vcodec, acodec, crf, video_bitrate,
                    audio_bitrate, resolution, fps, format, hw_accel, extra
      audio_mix   : list of {audio_index: int, muted: bool, volume: float}

    Raises ValueError if the file is not a recognisable Clipper log.
    """
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    if not lines or "Export Log" not in lines[0]:
        raise ValueError("Not a Clipper export log file.")

    result: dict = {
        "input_path":  "",
        "output_path": "",
        "start_sec":   0.0,
        "end_sec":     0.0,
        "encoding": {k: "" for k in _ENCODING_KEYS.values()},
        "audio_mix":   [],
    }

    section = None
    for line in lines:
        stripped = line.strip()

        if stripped == "Encoding Parameters:":
            section = "encoding"
            continue
        if stripped == "Audio Mix:":
            section = "audio_mix"
            continue
        if stripped == "FFmpeg Command:":
            section = None
            continue

        if line.startswith("Input:"):
            result["input_path"] = line[len("Input:"):].strip()
        elif line.startswith("Output:"):
            result["output_path"] = line[len("Output:"):].strip()
        elif line.startswith("Start:"):
            result["start_sec"] = _tc_to_seconds(line[len("Start:"):].strip())
        elif line.startswith("End:"):
            result["end_sec"] = _tc_to_seconds(line[len("End:"):].strip())
        elif section == "encoding" and line.startswith("  ") and ":" in stripped:
            key, _, val = stripped.partition(":")
            enc_key = _ENCODING_KEYS.get(key.strip())
            if enc_key:
                v = val.strip()
                result["encoding"][enc_key] = "" if v in _PLACEHOLDERS else v
        elif section == "audio_mix" and stripped.startswith("Track "):
            m = re.match(r"Track (\d+):\s*(.*)", stripped)
            if m:
                track_num = int(m.group(1))
                rest = m.group(2).strip()
                if rest == "muted":
                    result["audio_mix"].append(
                        {"audio_index": track_num - 1, "muted": True, "volume": 1.0}
                    )
                else:
                    vm = re.match(r"volume (\d+)%", rest)
                    if vm:
                        result["audio_mix"].append({
                            "audio_index": track_num - 1,
                            "muted":       False,
                            "volume":      int(vm.group(1)) / 100.0,
                        })

    return result
