"""
ui/player_widget.py
Video playback widget using Qt's QMediaPlayer + QVideoWidget.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QFrame, QSlider, QButtonGroup
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont


class VideoPlayerWidget(QWidget):
    """
    Central video player area containing:
    - QVideoWidget for display
    - Transport controls (play/pause, stop, frame step)
    - Current timecode display
    - Per-stream audio mix controls
    """

    position_changed = pyqtSignal(float)   # current position in seconds
    duration_changed = pyqtSignal(float)   # total duration in seconds
    media_loaded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 0.0
        self._fps = 30.0
        self._audio_streams = []
        self._stream_rows = []     # list of {monitor_btn, mute_btn, vol_slider, vol_label, stream}
        self._monitor_group = QButtonGroup(self)
        self._monitor_group.setExclusive(True)
        self._setup_player()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video display
        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("videoWidget")
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_widget.setMinimumSize(640, 360)
        self.player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)

        # Drop hint overlay (shown when no video loaded)
        self.drop_label = QLabel("Drop a video file here\nor use File → Open")
        self.drop_label.setObjectName("dropLabel")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setParent(self.video_widget)
        self.drop_label.resize(self.video_widget.size())

        # Controls bar
        controls = QFrame()
        controls.setObjectName("controlsBar")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(12, 8, 12, 8)
        ctrl_layout.setSpacing(8)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("btnPlay")
        self.btn_play.setFixedSize(44, 44)
        self.btn_play.setToolTip("Play / Pause  [Space]")

        self.btn_stop = QPushButton("■")
        self.btn_stop.setObjectName("btnTransport")
        self.btn_stop.setFixedSize(36, 36)
        self.btn_stop.setToolTip("Stop")

        self.btn_frame_back = QPushButton("◀|")
        self.btn_frame_back.setObjectName("btnTransport")
        self.btn_frame_back.setFixedSize(36, 36)
        self.btn_frame_back.setToolTip("Previous Frame  [,]")

        self.btn_frame_fwd = QPushButton("|▶")
        self.btn_frame_fwd.setObjectName("btnTransport")
        self.btn_frame_fwd.setFixedSize(36, 36)
        self.btn_frame_fwd.setToolTip("Next Frame  [.]")

        self.timecode_label = QLabel("00:00:00.000  /  00:00:00.000")
        self.timecode_label.setObjectName("timecodeLabel")

        self.volume_label = QLabel("🔊")
        self.volume_label.setObjectName("volumeLabel")

        ctrl_layout.addWidget(self.btn_frame_back)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_frame_fwd)
        ctrl_layout.addSpacing(16)
        ctrl_layout.addWidget(self.timecode_label)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.volume_label)

        layout.addWidget(controls)

        # Audio mix bar (hidden until streams are loaded)
        self.audio_mix_bar = QFrame()
        self.audio_mix_bar.setObjectName("audioMixBar")
        self._audio_mix_layout = QVBoxLayout(self.audio_mix_bar)
        self._audio_mix_layout.setContentsMargins(12, 6, 12, 6)
        self._audio_mix_layout.setSpacing(3)

        self.audio_mix_bar.setVisible(False)
        layout.addWidget(self.audio_mix_bar)

    def _connect_signals(self):
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_frame_back.clicked.connect(self.step_back)
        self.btn_frame_fwd.clicked.connect(self.step_forward)

        self._monitor_group.idClicked.connect(self._on_monitor_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str, fps: float = 30.0):
        self._fps = fps
        self.player.setSource(QUrl.fromLocalFile(path))
        self.drop_label.hide()
        self.media_loaded.emit()

    def unload(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.drop_label.show()
        self._update_timecode(0)
        self._duration = 0.0

    def set_audio_streams(self, streams: list):
        """Populate the audio mix bar with per-stream controls."""
        # Clear previous rows
        for row in self._stream_rows:
            row["widget"].deleteLater()
        self._stream_rows.clear()
        for btn in self._monitor_group.buttons():
            self._monitor_group.removeButton(btn)

        self._audio_streams = streams

        for s in streams:
            aidx = s["audio_index"]

            row_widget = QWidget()
            row_widget.setObjectName("audioStreamRow")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Stream label
            parts = [f"A{aidx + 1}"]
            if s.get("language"):
                parts.append(s["language"])
            if s.get("title"):
                parts.append(s["title"])
            layout_str = s.get("channel_layout", "")
            if layout_str:
                parts.append(f"[{layout_str}]")
            lbl = QLabel("  ".join(parts))
            lbl.setObjectName("audioStreamLabel")
            lbl.setMinimumWidth(130)
            lbl.setMaximumWidth(200)

            # Monitor button (radio — selects playback track)
            mon_btn = QPushButton("Monitor")
            mon_btn.setObjectName("btnAudioMonitor")
            mon_btn.setCheckable(True)
            mon_btn.setFixedWidth(72)
            mon_btn.setToolTip("Listen to this track during playback")
            self._monitor_group.addButton(mon_btn, aidx)
            if aidx == 0:
                mon_btn.setChecked(True)

            # Mute button
            mute_btn = QPushButton("🔊")
            mute_btn.setObjectName("btnAudioMute")
            mute_btn.setCheckable(True)
            mute_btn.setFixedWidth(34)
            mute_btn.setToolTip("Mute this stream in export (and playback when monitored)")

            # Volume slider (0–200, representing 0%–200%)
            vol_slider = QSlider(Qt.Orientation.Horizontal)
            vol_slider.setObjectName("audioVolSlider")
            vol_slider.setRange(0, 200)
            vol_slider.setValue(100)
            vol_slider.setFixedWidth(110)
            vol_slider.setToolTip("Volume for this stream (applies to export)")

            vol_label = QLabel("100%")
            vol_label.setObjectName("audioVolLabel")
            vol_label.setFixedWidth(38)

            row_layout.addWidget(lbl)
            row_layout.addWidget(mon_btn)
            row_layout.addWidget(mute_btn)
            row_layout.addWidget(vol_slider)
            row_layout.addWidget(vol_label)
            row_layout.addStretch()

            self._audio_mix_layout.addWidget(row_widget)

            entry = {
                "widget": row_widget,
                "stream": s,
                "monitor_btn": mon_btn,
                "mute_btn": mute_btn,
                "vol_slider": vol_slider,
                "vol_label": vol_label,
            }
            self._stream_rows.append(entry)

            # Connect signals using closures
            def _make_vol_handler(e):
                def handler(val):
                    e["vol_label"].setText(f"{val}%")
                    # Update playback volume if this is the monitored stream
                    if self._monitor_group.checkedId() == e["stream"]["audio_index"]:
                        effective = 0.0 if e["mute_btn"].isChecked() else val / 100.0
                        self.audio_output.setVolume(effective)
                return handler

            def _make_mute_handler(e):
                def handler(checked):
                    e["mute_btn"].setText("🔇" if checked else "🔊")
                    if self._monitor_group.checkedId() == e["stream"]["audio_index"]:
                        effective = 0.0 if checked else e["vol_slider"].value() / 100.0
                        self.audio_output.setVolume(effective)
                return handler

            vol_slider.valueChanged.connect(_make_vol_handler(entry))
            mute_btn.toggled.connect(_make_mute_handler(entry))

        # Show bar only if there are streams
        self.audio_mix_bar.setVisible(len(streams) > 0)

        # Set initial playback track
        if streams:
            self.player.setActiveAudioTrack(0)

    def get_audio_mix_config(self) -> list:
        """Return per-stream mix settings for use by ExportWorker."""
        result = []
        for row in self._stream_rows:
            result.append({
                "audio_index": row["stream"]["audio_index"],
                "stream_index": row["stream"]["stream_index"],
                "mute": row["mute_btn"].isChecked(),
                "volume": row["vol_slider"].value() / 100.0,
            })
        return result

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, seconds: float):
        self.player.setPosition(int(seconds * 1000))

    def get_position(self) -> float:
        return self.player.position() / 1000.0

    def step_forward(self):
        frame_ms = int(1000.0 / max(self._fps, 1))
        new_pos = min(self.player.position() + frame_ms, self.player.duration())
        self.player.setPosition(new_pos)

    def step_back(self):
        frame_ms = int(1000.0 / max(self._fps, 1))
        new_pos = max(self.player.position() - frame_ms, 0)
        self.player.setPosition(new_pos)

    def set_volume(self, value: float):
        self.audio_output.setVolume(value)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_monitor_changed(self, audio_index: int):
        """Switch the active playback track and update audio output volume."""
        self.player.setActiveAudioTrack(audio_index)
        # Apply the mute/volume of the newly monitored stream
        for row in self._stream_rows:
            if row["stream"]["audio_index"] == audio_index:
                muted = row["mute_btn"].isChecked()
                vol = row["vol_slider"].value() / 100.0
                self.audio_output.setVolume(0.0 if muted else vol)
                break

    def _on_position_changed(self, ms: int):
        seconds = ms / 1000.0
        self._update_timecode(seconds)
        self.position_changed.emit(seconds)

    def _on_duration_changed(self, ms: int):
        self._duration = ms / 1000.0
        self.duration_changed.emit(self._duration)
        self._update_timecode(0)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")

    def _update_timecode(self, seconds: float):
        self.timecode_label.setText(
            f"{self._format_tc(seconds)}  /  {self._format_tc(self._duration)}"
        )

    @staticmethod
    def _format_tc(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds * 1000) % 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    # ------------------------------------------------------------------
    # Resize handler
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.drop_label.resize(self.video_widget.size())
