"""
ui/export_panel.py
Right-hand panel for configuring and running the export.
"""

import json
import os
import shlex
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QFileDialog, QLineEdit, QInputDialog,
    QCheckBox, QDoubleSpinBox, QFormLayout,
    QScrollArea, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QFont

from core.constants import SERVICE_NAME
from core.ffmpeg_worker import EXPORT_PRESETS, HW_ACCEL_OPTIONS, _parse_bitrate_bps


class ExportPanel(QWidget):
    """
    Panel containing:
    - In/Out timecode displays
    - Platform preset loader with save/delete for custom presets
    - Editable encoding parameter fields
    - Hardware acceleration selector
    - Target file size mode
    - Output directory + filename fields
    - Export button + progress bar
    - FFmpeg log viewer
    """

    export_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("exportPanel")
        self.setMinimumWidth(380)
        self._in_sec = 0.0
        self._out_sec = 0.0
        self._custom_presets: dict[str, dict] = {}
        self._load_custom_presets()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # Title
        title = QLabel("EXPORT")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        # ── Clip info ──────────────────────────────────────────────────
        clip_group = QGroupBox("Clip Range")
        clip_group.setObjectName("panelGroup")
        clip_layout = QVBoxLayout(clip_group)
        clip_layout.setSpacing(6)

        def tc_row(label: str) -> tuple:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("tcLabel")
            lbl.setFixedWidth(28)
            val = QLabel("00:00:00.000")
            val.setObjectName("tcValue")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(val)
            return row, val

        in_row, self.lbl_in = tc_row("IN")
        out_row, self.lbl_out = tc_row("OUT")
        dur_row, self.lbl_dur = tc_row("DUR")
        clip_layout.addLayout(in_row)
        clip_layout.addLayout(out_row)
        clip_layout.addLayout(dur_row)
        layout.addWidget(clip_group)

        # ── Presets ────────────────────────────────────────────────────
        preset_group = QGroupBox("Presets")
        preset_group.setObjectName("panelGroup")
        preset_v = QVBoxLayout(preset_group)
        preset_v.setSpacing(6)
        preset_v.setContentsMargins(10, 14, 10, 10)

        # Row 1: combo + Apply
        load_row = QHBoxLayout()
        load_row.setSpacing(6)
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("presetCombo")
        self._refresh_preset_combo()
        btn_apply = QPushButton("Apply")
        btn_apply.setObjectName("btnBrowse")
        btn_apply.setFixedWidth(52)
        btn_apply.clicked.connect(lambda: self._load_preset_to_fields(self.preset_combo.currentText()))
        load_row.addWidget(self.preset_combo)
        load_row.addWidget(btn_apply)
        preset_v.addLayout(load_row)

        # Row 2: Save + Delete
        manage_row = QHBoxLayout()
        manage_row.setSpacing(6)
        btn_save_preset = QPushButton("Save as Preset…")
        btn_save_preset.setObjectName("btnBrowse")
        btn_save_preset.clicked.connect(self._on_save_preset_clicked)
        self.btn_delete_preset = QPushButton("Delete")
        self.btn_delete_preset.setObjectName("btnBrowse")
        self.btn_delete_preset.setFixedWidth(56)
        self.btn_delete_preset.clicked.connect(self._on_delete_preset_clicked)
        manage_row.addWidget(btn_save_preset)
        manage_row.addWidget(self.btn_delete_preset)
        preset_v.addLayout(manage_row)

        layout.addWidget(preset_group)

        self.preset_combo.currentTextChanged.connect(self._update_delete_btn_state)
        self._update_delete_btn_state(self.preset_combo.currentText())

        # ── Encoding parameters ────────────────────────────────────────
        enc_group = QGroupBox("Encoding Parameters")
        enc_group.setObjectName("panelGroup")
        enc_form = QFormLayout(enc_group)
        enc_form.setSpacing(6)
        enc_form.setContentsMargins(10, 14, 10, 10)
        enc_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        enc_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        def _field(placeholder: str) -> QLineEdit:
            w = QLineEdit()
            w.setObjectName("pathEdit")
            w.setPlaceholderText(placeholder)
            return w

        self.enc_vcodec     = _field("e.g. libx264")
        self.enc_acodec     = _field("e.g. aac  (or none)")
        self.enc_vbitrate   = _field("e.g. 8000k")
        self.enc_crf        = _field("0 – 51, e.g. 23")
        self.enc_abitrate   = _field("e.g. 192k")
        self.enc_resolution = _field("e.g. 1920x1080")
        self.enc_fps        = _field("e.g. 30")
        self.enc_format     = _field("e.g. mp4")
        self.enc_extra      = _field("extra ffmpeg args")

        self.enc_crf.setToolTip(
            "Constant Rate Factor — constant quality, variable file size.\n"
            "Overrides V-Bitrate when set. Disabled when Target File Size is active."
        )
        self.enc_vbitrate.setToolTip(
            "Target video bitrate. Ignored when CRF is set, or overridden by Target File Size."
        )

        self.hw_accel_combo = QComboBox()
        self.hw_accel_combo.setObjectName("presetCombo")
        for display_name in HW_ACCEL_OPTIONS:
            self.hw_accel_combo.addItem(display_name)

        enc_form.addRow("V-Codec:", self.enc_vcodec)
        enc_form.addRow("A-Codec:", self.enc_acodec)
        enc_form.addRow("V-Bitrate:", self.enc_vbitrate)
        enc_form.addRow("CRF:", self.enc_crf)
        enc_form.addRow("A-Bitrate:", self.enc_abitrate)
        enc_form.addRow("Resolution:", self.enc_resolution)
        enc_form.addRow("FPS:", self.enc_fps)
        enc_form.addRow("Format:", self.enc_format)
        enc_form.addRow("Extra:", self.enc_extra)
        enc_form.addRow("HW Accel:", self.hw_accel_combo)

        layout.addWidget(enc_group)

        # ── Target file size ───────────────────────────────────────────
        size_group = QGroupBox("Target File Size")
        size_group.setObjectName("panelGroup")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(5)
        size_layout.setContentsMargins(10, 14, 10, 10)

        self.target_size_check = QCheckBox("Enable target size")
        size_layout.addWidget(self.target_size_check)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self.target_size_spin = QDoubleSpinBox()
        self.target_size_spin.setObjectName("pathEdit")
        self.target_size_spin.setRange(0.1, 100_000.0)
        self.target_size_spin.setValue(50.0)
        self.target_size_spin.setSuffix(" MB")
        self.target_size_spin.setDecimals(1)
        self.target_size_spin.setEnabled(False)
        size_row.addWidget(self.target_size_spin)

        self.target_size_est = QLabel("")
        self.target_size_est.setObjectName("presetInfo")
        size_row.addWidget(self.target_size_est)
        size_row.addStretch()
        size_layout.addLayout(size_row)
        layout.addWidget(size_group)

        self.target_size_check.toggled.connect(self._on_target_size_toggled)
        self.target_size_spin.valueChanged.connect(self._update_target_size_estimate)

        # ── Output file ────────────────────────────────────────────────
        out_group = QGroupBox("Output File")
        out_group.setObjectName("panelGroup")
        out_layout = QVBoxLayout(out_group)
        out_layout.setContentsMargins(10, 14, 10, 10)
        out_layout.setSpacing(6)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(4)
        dir_lbl = QLabel("Folder:")
        dir_lbl.setObjectName("tcLabel")
        dir_lbl.setFixedWidth(52)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setObjectName("pathEdit")
        self.output_dir_edit.setPlaceholderText("Output folder…")
        btn_browse_dir = QPushButton("…")
        btn_browse_dir.setFixedWidth(32)
        btn_browse_dir.setObjectName("btnBrowse")
        btn_browse_dir.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(dir_lbl)
        dir_row.addWidget(self.output_dir_edit)
        dir_row.addWidget(btn_browse_dir)
        out_layout.addLayout(dir_row)

        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        name_lbl = QLabel("Filename:")
        name_lbl.setObjectName("tcLabel")
        name_lbl.setFixedWidth(52)
        self.output_filename_edit = QLineEdit()
        self.output_filename_edit.setObjectName("pathEdit")
        self.output_filename_edit.setPlaceholderText("e.g. clip_export.mp4")
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.output_filename_edit)
        out_layout.addLayout(name_row)

        self.save_log_check = QCheckBox("Save encoding params as .txt")
        self.save_log_check.setChecked(True)
        out_layout.addWidget(self.save_log_check)

        layout.addWidget(out_group)

        # ── Export button ──────────────────────────────────────────────
        self.btn_export = QPushButton("⬇  Export Clip")
        self.btn_export.setObjectName("btnExport")
        self.btn_export.setFixedHeight(46)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_requested)
        layout.addWidget(self.btn_export)

        self.btn_cancel = QPushButton("✕  Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self.cancel_requested)
        layout.addWidget(self.btn_cancel)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("exportProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ── FFmpeg log ─────────────────────────────────────────────────
        log_group = QGroupBox("FFmpeg Log")
        log_group.setObjectName("panelGroup")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        self.log_view.setFont(QFont("Courier New", 8))
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        layout.addStretch()

        # Load default preset into fields
        self._load_preset_to_fields(self.preset_combo.currentText())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_in_out(self, in_sec: float, out_sec: float):
        self._in_sec = in_sec
        self._out_sec = out_sec
        self.lbl_in.setText(self._fmt(in_sec))
        self.lbl_out.setText(self._fmt(out_sec))
        self.lbl_dur.setText(self._fmt(out_sec - in_sec))
        self._update_target_size_estimate()

    def set_ready(self, ready: bool):
        self.btn_export.setEnabled(ready)

    def get_export_config(self) -> dict:
        """Return the current encoding parameters as a preset-compatible dict."""
        vcodec = self.enc_vcodec.text().strip() or "libx264"
        acodec_raw = self.enc_acodec.text().strip().lower()
        acodec = None if acodec_raw in ("none", "") else (acodec_raw or "aac")

        extra_text = self.enc_extra.text().strip()
        try:
            extra = shlex.split(extra_text) if extra_text else []
        except ValueError:
            extra = extra_text.split()

        return {
            "vcodec": vcodec,
            "acodec": acodec,
            "video_bitrate": self.enc_vbitrate.text().strip() or None,
            "crf": self.enc_crf.text().strip() or None,
            "audio_bitrate": self.enc_abitrate.text().strip() or None,
            "resolution": self.enc_resolution.text().strip() or None,
            "fps": self.enc_fps.text().strip() or None,
            "format": self.enc_format.text().strip() or "mp4",
            "extra": extra,
        }

    def get_target_size_mb(self) -> Optional[float]:
        if self.target_size_check.isChecked():
            return self.target_size_spin.value()
        return None

    def get_hw_accel(self) -> str:
        display_name = self.hw_accel_combo.currentText()
        return HW_ACCEL_OPTIONS.get(display_name, "")

    def get_save_log(self) -> bool:
        return self.save_log_check.isChecked()

    def get_output_path(self) -> str:
        dir_ = self.output_dir_edit.text().strip()
        name = self.output_filename_edit.text().strip()
        if not name:
            return ""
        return os.path.join(dir_, name) if dir_ else name

    def set_output_path(self, path: str):
        if path:
            self.output_dir_edit.setText(os.path.dirname(path))
            self.output_filename_edit.setText(os.path.basename(path))
        else:
            self.output_dir_edit.setText("")
            self.output_filename_edit.setText("")

    def set_exporting(self, exporting: bool):
        self.btn_export.setVisible(not exporting)
        self.btn_cancel.setVisible(exporting)
        self.progress_bar.setVisible(exporting)
        if exporting:
            self.progress_bar.setValue(0)
            self.log_view.clear()
            self.status_label.setText("Exporting…")
        else:
            self.status_label.setText("")

    def update_progress(self, value: int):
        self.progress_bar.setValue(value)

    def append_log(self, line: str):
        self.log_view.append(line)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_status(self, msg: str, is_error: bool = False):
        color = "#ff6b6b" if is_error else "#00d4aa"
        self.status_label.setText(f'<span style="color:{color}">{msg}</span>')

    # ------------------------------------------------------------------
    # Custom preset persistence
    # ------------------------------------------------------------------

    def _settings(self) -> QSettings:
        return QSettings(SERVICE_NAME, SERVICE_NAME)

    def _load_custom_presets(self):
        s = self._settings()
        raw = s.value("export_custom_presets", "[]")
        try:
            entries = json.loads(raw)
            self._custom_presets = {e["name"]: e["config"] for e in entries}
        except Exception:
            self._custom_presets = {}

    def _persist_custom_presets(self):
        entries = [{"name": n, "config": c} for n, c in self._custom_presets.items()]
        self._settings().setValue("export_custom_presets", json.dumps(entries))

    def _refresh_preset_combo(self):
        current = self.preset_combo.currentText() if hasattr(self, "preset_combo") else ""
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in EXPORT_PRESETS:
            self.preset_combo.addItem(name)
        if self._custom_presets:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in self._custom_presets:
                self.preset_combo.addItem(name)
        # Restore selection if still present
        idx = self.preset_combo.findText(current)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def _update_delete_btn_state(self, name: str):
        self.btn_delete_preset.setEnabled(name in self._custom_presets)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_save_preset_clicked(self):
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Preset name:",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in EXPORT_PRESETS:
            QMessageBox.warning(self, "Name Taken",
                                f'"{name}" is a built-in preset and cannot be overwritten.')
            return
        if name in self._custom_presets:
            reply = QMessageBox.question(
                self, "Overwrite?",
                f'A custom preset named "{name}" already exists. Overwrite it?',
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._custom_presets[name] = self.get_export_config()
        self._persist_custom_presets()
        self._refresh_preset_combo()
        # Select the newly saved preset
        idx = self.preset_combo.findText(name)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self._update_delete_btn_state(name)

    def _on_delete_preset_clicked(self):
        name = self.preset_combo.currentText()
        if name not in self._custom_presets:
            return
        reply = QMessageBox.question(
            self, "Delete Preset",
            f'Delete the custom preset "{name}"?',
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        del self._custom_presets[name]
        self._persist_custom_presets()
        self._refresh_preset_combo()
        self._update_delete_btn_state(self.preset_combo.currentText())

    def _load_preset_to_fields(self, name: str):
        p = EXPORT_PRESETS.get(name) or self._custom_presets.get(name)
        if p is None:
            return
        self.enc_vcodec.setText(p.get("vcodec") or "")
        self.enc_acodec.setText(p.get("acodec") or "")
        self.enc_vbitrate.setText(p.get("video_bitrate") or "")
        self.enc_crf.setText(p.get("crf") or "")
        self.enc_abitrate.setText(p.get("audio_bitrate") or "")
        self.enc_resolution.setText(p.get("resolution") or "")
        self.enc_fps.setText(p.get("fps") or "")
        self.enc_format.setText(p.get("format") or "")
        self.enc_extra.setText(" ".join(p.get("extra", [])))
        self._update_target_size_estimate()

    def _on_target_size_toggled(self, checked: bool):
        self.target_size_spin.setEnabled(checked)
        self.enc_vbitrate.setEnabled(not checked)
        self.enc_crf.setEnabled(not checked)
        if checked:
            self.enc_vbitrate.setPlaceholderText("(computed from target size)")
            self.enc_vbitrate.clear()
            self.enc_crf.setPlaceholderText("(disabled — target size active)")
            self.enc_crf.clear()
        else:
            self.enc_vbitrate.setPlaceholderText("e.g. 8000k")
            self.enc_crf.setPlaceholderText("0 – 51, e.g. 23")
        self._update_target_size_estimate()

    def _update_target_size_estimate(self):
        if not self.target_size_check.isChecked():
            self.target_size_est.setText("")
            return
        duration = self._out_sec - self._in_sec
        if duration <= 0:
            self.target_size_est.setText("")
            return
        target_bytes = self.target_size_spin.value() * 1024 * 1024
        total_bps = (target_bytes * 8) / duration
        audio_bps = _parse_bitrate_bps(self.enc_abitrate.text().strip() or None)
        video_bps = max(0, total_bps - audio_bps)
        self.target_size_est.setText(f"~{int(video_bps / 1000)} kbps")

    def _browse_output_dir(self):
        start = self.output_dir_edit.text().strip() or ""
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", start)
        if path:
            self.output_dir_edit.setText(path)

    @staticmethod
    def _fmt(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds * 1000) % 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
