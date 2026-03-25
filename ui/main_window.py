"""
ui/main_window.py
Main application window — wires player, timeline, and export panel together.
"""

import os
import shutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QFileDialog, QMessageBox, QLabel,
    QMenuBar, QStatusBar, QDockWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from ui.player_widget import VideoPlayerWidget
from ui.timeline_widget import TimelineWidget
from ui.export_panel import ExportPanel
from core.ffmpeg_worker import probe_video, VideoInfo, ExportWorker
from core.constants import SERVICE_NAME


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(SERVICE_NAME)
        self.setMinimumSize(1100, 680)
        self.resize(1280, 760)
        self.setAcceptDrops(True)

        self._video_info: VideoInfo = None
        self._export_worker: ExportWorker = None
        self._points_modified: bool = False

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left: player + timeline
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.player = VideoPlayerWidget()
        left_layout.addWidget(self.player, stretch=1)

        # Timeline
        timeline_container = QWidget()
        timeline_container.setObjectName("timelineContainer")
        tl_layout = QVBoxLayout(timeline_container)
        tl_layout.setContentsMargins(8, 4, 8, 8)
        tl_layout.setSpacing(4)

        self.timeline = TimelineWidget()
        tl_layout.addWidget(self.timeline)

        # In/Out button bar under timeline
        io_bar = QHBoxLayout()
        from PyQt6.QtWidgets import QPushButton
        self.btn_set_in = QPushButton("[I]  Set In Point")
        self.btn_set_in.setObjectName("btnIO")
        self.btn_set_out = QPushButton("Set Out Point  [O]")
        self.btn_set_out.setObjectName("btnIO")
        self.btn_reset_io = QPushButton("↺  Reset Range")
        self.btn_reset_io.setObjectName("btnIOSecondary")
        self.btn_unload = QPushButton("✕  Unload")
        self.btn_unload.setObjectName("btnIOSecondary")
        self.btn_unload.setToolTip("Unload the current video")
        self.btn_unload.setEnabled(False)

        io_bar.addWidget(self.btn_set_in)
        io_bar.addWidget(self.btn_set_out)
        io_bar.addStretch()
        io_bar.addWidget(self.btn_reset_io)
        io_bar.addWidget(self.btn_unload)
        tl_layout.addLayout(io_bar)

        left_layout.addWidget(timeline_container)

        # Right: export panel
        self.export_panel = ExportPanel()

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.export_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(2)

        root.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_perm = QLabel("No video loaded")
        self.status_bar.addPermanentWidget(self._status_perm)

        # Connect signals
        self.player.position_changed.connect(self.timeline.set_position)
        self.player.duration_changed.connect(self._on_duration_changed)

        self.timeline.seek_requested.connect(self.player.seek)
        self.timeline.in_point_changed.connect(self._on_in_point_changed)
        self.timeline.out_point_changed.connect(self._on_out_point_changed)

        self.btn_set_in.clicked.connect(
            lambda: self.timeline.set_in_point(self.player.get_position())
        )
        self.btn_set_out.clicked.connect(
            lambda: self.timeline.set_out_point(self.player.get_position())
        )
        self.btn_reset_io.clicked.connect(self._reset_points)

        self.export_panel.export_requested.connect(self._start_export)
        self.export_panel.cancel_requested.connect(self._cancel_export)
        self.btn_unload.clicked.connect(self._unload_video)

    def _build_menu(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")

        act_open = QAction("&Open Video…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file_dialog)
        file_menu.addAction(act_open)

        self._act_unload = QAction("&Unload Video", self)
        self._act_unload.triggered.connect(self._unload_video)
        self._act_unload.setEnabled(False)
        file_menu.addAction(self._act_unload)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Playback menu
        pb_menu = mb.addMenu("&Playback")

        act_play = QAction("Play / Pause", self)
        act_play.setShortcut(Qt.Key.Key_Space)
        act_play.triggered.connect(self.player.toggle_play)
        pb_menu.addAction(act_play)

        act_in = QAction("Set &In Point", self)
        act_in.setShortcut(Qt.Key.Key_I)
        act_in.triggered.connect(lambda: self.timeline.set_in_point(self.player.get_position()))
        pb_menu.addAction(act_in)

        act_out = QAction("Set &Out Point", self)
        act_out.setShortcut(Qt.Key.Key_O)
        act_out.triggered.connect(lambda: self.timeline.set_out_point(self.player.get_position()))
        pb_menu.addAction(act_out)

        pb_menu.addSeparator()

        act_frame_back = QAction("Previous Frame", self)
        act_frame_back.setShortcut(Qt.Key.Key_Comma)
        act_frame_back.triggered.connect(self.player.step_back)
        pb_menu.addAction(act_frame_back)

        act_frame_fwd = QAction("Next Frame", self)
        act_frame_fwd.setShortcut(Qt.Key.Key_Period)
        act_frame_fwd.triggered.connect(self.player.step_forward)
        pb_menu.addAction(act_frame_fwd)

    def _build_shortcuts(self):
        pass  # Shortcuts are set in menu actions

    # ------------------------------------------------------------------
    # File Loading
    # ------------------------------------------------------------------

    def _open_file_dialog(self):
        if not self._confirm_replace():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video File", "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.flv *.wmv *.mxf);;All Files (*)"
        )
        if path:
            self._load_video(path)

    def _confirm_replace(self) -> bool:
        """Return True if it's safe to load a new file. Prompts if points were modified."""
        if not self._video_info:
            return True
        if not self._points_modified:
            return True
        reply = QMessageBox.question(
            self, "Replace Video?",
            "You have unsaved in/out points.\nLoad a new video and discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _unload_video(self):
        if self._export_worker and self._export_worker.isRunning():
            QMessageBox.warning(self, "Export in Progress",
                                "Cannot unload while an export is running.")
            return
        if self._points_modified:
            reply = QMessageBox.question(
                self, "Unload Video?",
                "You have unsaved in/out points.\nUnload the video and discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.player.unload()
        self.player.set_audio_streams([])
        self.timeline.set_duration(0)
        self.timeline.reset_points()
        self.export_panel.set_ready(False)
        self.export_panel.set_in_out(0.0, 0.0)
        self.export_panel.set_output_path("")
        self._video_info = None
        self._points_modified = False
        self.btn_unload.setEnabled(False)
        self._act_unload.setEnabled(False)
        self._status_perm.setText("No video loaded")
        self.setWindowTitle(SERVICE_NAME)

    def _reset_points(self):
        self.timeline.reset_points()
        self._points_modified = False

    def _load_video(self, path: str):
        try:
            self._video_info = probe_video(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not probe video:\n{e}")
            return

        info = self._video_info
        self.player.load(path, fps=info.fps)
        self.player.set_audio_streams(info.audio_streams)
        self.timeline.set_duration(info.duration)
        self.timeline.reset_points()
        self._points_modified = False
        self.export_panel.set_ready(True)
        self.export_panel.set_in_out(0.0, info.duration)
        self.btn_unload.setEnabled(True)
        self._act_unload.setEnabled(True)

        # Suggest output path
        base = os.path.splitext(path)[0]
        ext = self.export_panel.get_export_config()["format"]
        self.export_panel.set_output_path(f"{base}_export.{ext}")

        # Update status
        size_mb = info.size_bytes / (1024 * 1024)
        self._status_perm.setText(
            f"{os.path.basename(path)}  |  "
            f"{info.width}×{info.height}  {info.fps:.2f}fps  |  "
            f"{info.video_codec}/{info.audio_codec}  |  "
            f"{size_mb:.1f} MB"
        )
        self.setWindowTitle(f"{SERVICE_NAME} — {os.path.basename(path)}")

    # ------------------------------------------------------------------
    # Timeline callbacks
    # ------------------------------------------------------------------

    def _on_duration_changed(self, dur: float):
        self.timeline.set_duration(dur)

    def _on_in_point_changed(self, sec: float):
        self._points_modified = True
        self.export_panel.set_in_out(sec, self.timeline.get_out_point())

    def _on_out_point_changed(self, sec: float):
        self._points_modified = True
        self.export_panel.set_in_out(self.timeline.get_in_point(), sec)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _start_export(self):
        if not self._video_info:
            QMessageBox.warning(self, "No Video", "Please load a video first.")
            return

        output_path = self.export_panel.get_output_path()
        if not output_path:
            QMessageBox.warning(self, "No Output Path", "Please choose an output file path.")
            return

        in_pt = self.timeline.get_in_point()
        out_pt = self.timeline.get_out_point()
        if out_pt <= in_pt:
            QMessageBox.warning(self, "Invalid Range", "Out point must be after in point.")
            return

        if os.path.exists(output_path):
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"File already exists:\n{output_path}\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._export_worker = ExportWorker(
            input_path=self._video_info.path,
            output_path=output_path,
            start_sec=in_pt,
            end_sec=out_pt,
            preset_config=self.export_panel.get_export_config(),
            target_size_mb=self.export_panel.get_target_size_mb(),
            hw_accel=self.export_panel.get_hw_accel(),
            audio_mix=self.player.get_audio_mix_config() or None,
            save_log=self.export_panel.get_save_log(),
        )
        self._export_worker.progress.connect(self.export_panel.update_progress)
        self._export_worker.log_line.connect(self.export_panel.append_log)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)

        self.export_panel.set_exporting(True)
        self._export_worker.start()

    def _cancel_export(self):
        if self._export_worker:
            self._export_worker.cancel()
        self.export_panel.set_exporting(False)
        self.export_panel.set_status("Export cancelled.", is_error=True)

    def _on_export_finished(self, path: str):
        self.export_panel.set_exporting(False)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        self.export_panel.set_status(f"✓ Exported: {os.path.basename(path)}  ({size_mb:.1f} MB)")
        QMessageBox.information(
            self, "Export Complete",
            f"Clip exported successfully!\n\n{path}\n({size_mb:.1f} MB)"
        )

    def _on_export_error(self, msg: str):
        self.export_panel.set_exporting(False)
        self.export_panel.set_status(f"✗ {msg}", is_error=True)
        QMessageBox.critical(self, "Export Failed", msg)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.isLocalFile():
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if not self._confirm_replace():
            return
        url = event.mimeData().urls()[0]
        path = url.toLocalFile()
        self._load_video(path)
