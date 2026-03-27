"""
ui/theme_editor.py
Live theme editor — lets the user build and save custom colour themes.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QScrollArea, QWidget, QGroupBox, QFrame, QMessageBox,
    QColorDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ui.themes import ThemeManager, THEMES, BUILTIN_THEME_NAMES


# ──────────────────────────────────────────────────────────────────────────────
# Palette key groups for the editor UI
# ──────────────────────────────────────────────────────────────────────────────

_GROUPS = [
    ("Backgrounds", [
        ("bg_deepest",      "Deepest"),
        ("bg_base",         "Base"),
        ("bg_surface",      "Surface"),
        ("bg_elevated",     "Elevated"),
        ("bg_input",        "Input fields"),
        ("bg_io",           "IO buttons"),
        ("bg_button",       "Buttons / borders"),
        ("bg_button_hover", "Button hover"),
        ("bg_group",        "Group boxes"),
        ("bg_menu",         "Menu / panel"),
        ("bg_selected",     "Selection"),
    ]),
    ("Accent", [
        ("accent",         "Primary"),
        ("accent_bright",  "Hover"),
        ("accent_dim",     "Pressed"),
        ("accent_bg",      "Tint background"),
    ]),
    ("Danger", [
        ("danger",    "Colour"),
        ("danger_bg", "Background"),
    ]),
    ("Borders", [
        ("border_io",     "IO border"),
        ("border_io_dim", "IO border dim"),
    ]),
    ("Text", [
        ("text_primary",   "Primary"),
        ("text_secondary", "Secondary"),
        ("text_muted",     "Muted"),
        ("text_faint",     "Faint"),
        ("text_log",       "Log viewer"),
    ]),
]


# ──────────────────────────────────────────────────────────────────────────────
# Colour swatch button
# ──────────────────────────────────────────────────────────────────────────────

class _Swatch(QPushButton):
    """A fixed-size button that displays a colour and opens QColorDialog on click."""

    def __init__(self, hex_color: str, key: str, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self._key = key
        self._callback = None
        self.setFixedSize(92, 22)
        self.setToolTip(key)
        self._refresh()
        self.clicked.connect(self._pick)

    # ------------------------------------------------------------------

    def set_hex(self, hex_color: str) -> None:
        self._hex = hex_color
        self._refresh()

    @property
    def hex_color(self) -> str:
        return self._hex

    def on_change(self, callback) -> None:
        """Register a callback(key, hex_str) called when the colour changes."""
        self._callback = callback

    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        r = int(self._hex[1:3], 16)
        g = int(self._hex[3:5], 16)
        b = int(self._hex[5:7], 16)
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        fg = "#000000" if lum > 0.45 else "#ffffff"
        # Widget-level stylesheet beats app-level QSS for this button.
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {self._hex};"
            f"  color: {fg};"
            f"  border: 1px solid rgba(128,128,128,0.5);"
            f"  border-radius: 3px;"
            f"  font-family: 'Courier New', monospace;"
            f"  font-size: 10px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  border: 2px solid rgba(255,255,255,0.8);"
            f"}}"
        )
        self.setText(self._hex)

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._hex), self, f"Choose colour — {self._key}")
        if color.isValid():
            self._hex = color.name().lower()
            self._refresh()
            if self._callback:
                self._callback(self._key, self._hex)


# ──────────────────────────────────────────────────────────────────────────────
# Editor dialog
# ──────────────────────────────────────────────────────────────────────────────

class ThemeEditorDialog(QDialog):
    """
    Modeless dialog for creating custom themes.
    Changes are applied live to the running application.
    Closing without saving restores the theme that was active on open.
    """

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Theme Editor")
        self.resize(600, 680)
        self.setModal(False)

        self._tm = theme_manager
        self._restore_name = theme_manager.current_theme
        self._palette: dict[str, str] = dict(theme_manager.palette)
        self._swatches: dict[str, _Swatch] = {}
        self._cleaned_up = False  # prevents double-restore on cancel + closeEvent

        self._build_ui()
        self._populate(self._palette)

        # If the user changes theme via the main menu while editor is open,
        # keep the editor palette in sync.
        self._tm.theme_changed.connect(self._on_external_change)

    # ──────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Top bar ────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        top.addWidget(QLabel("Start from:"))
        self._base_combo = QComboBox()
        self._base_combo.addItems(list(THEMES.keys()))
        self._base_combo.setCurrentText(self._restore_name)
        self._base_combo.setFixedWidth(150)
        self._base_combo.currentTextChanged.connect(self._on_base_changed)
        top.addWidget(self._base_combo)

        top.addSpacing(20)
        top.addWidget(QLabel("Theme name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter a name…")
        self._name_edit.setFixedWidth(180)
        top.addWidget(self._name_edit)

        top.addStretch()
        root.addLayout(top)

        # Inline error label (hidden until needed)
        self._err_label = QLabel()
        self._err_label.setStyleSheet("color: #ff6060; font-size: 11px;")
        self._err_label.hide()
        root.addWidget(self._err_label)

        # ── Colour pickers ─────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        cols = QHBoxLayout(inner)
        cols.setSpacing(12)
        cols.setContentsMargins(0, 0, 4, 0)

        # Left column: Backgrounds
        left = QVBoxLayout()
        left.setSpacing(8)
        self._add_group(left, _GROUPS[0])
        left.addStretch()

        # Right column: Accent + Danger + Borders + Text
        right = QVBoxLayout()
        right.setSpacing(8)
        for grp in _GROUPS[1:]:
            self._add_group(right, grp)
        right.addStretch()

        cols.addLayout(left, stretch=1)
        cols.addLayout(right, stretch=1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(30)
        btn_cancel.clicked.connect(self._cancel)

        btn_save = QPushButton("Save Theme")
        btn_save.setObjectName("btnExport")
        btn_save.setFixedHeight(30)
        btn_save.setMinimumWidth(110)
        btn_save.clicked.connect(self._save)

        btn_row.addWidget(btn_cancel)
        btn_row.addSpacing(6)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

    def _add_group(self, col: QVBoxLayout, group_def: tuple) -> None:
        name, keys = group_def
        box = QGroupBox(name)
        box.setObjectName("panelGroup")
        grid = QGridLayout(box)
        grid.setSpacing(5)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setColumnStretch(0, 1)

        for row, (key, label) in enumerate(keys):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            swatch = _Swatch("#000000", key)
            swatch.on_change(self._on_color_changed)
            self._swatches[key] = swatch
            grid.addWidget(lbl, row, 0)
            grid.addWidget(swatch, row, 1)

        col.addWidget(box)

    # ──────────────────────────────────────────────────────────────────
    # Logic
    # ──────────────────────────────────────────────────────────────────

    def _populate(self, palette: dict) -> None:
        for key, swatch in self._swatches.items():
            if key in palette:
                swatch.set_hex(palette[key])

    def _on_base_changed(self, theme_name: str) -> None:
        if theme_name in THEMES:
            self._palette = dict(THEMES[theme_name])
            self._populate(self._palette)
            self._tm.apply_palette(self._palette)

    def _on_color_changed(self, key: str, hex_val: str) -> None:
        self._palette[key] = hex_val
        self._tm.apply_palette(self._palette)

    def _on_external_change(self, theme_name: str, palette: dict) -> None:
        # Ignore our own live-preview signals; only react to real theme switches.
        if theme_name and theme_name != self._restore_name:
            self._restore_name = theme_name
            self._palette = dict(palette)
            self._populate(self._palette)
            self._base_combo.blockSignals(True)
            self._base_combo.setCurrentText(theme_name)
            self._base_combo.blockSignals(False)

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            self._show_error("Please enter a theme name.")
            return
        if name in BUILTIN_THEME_NAMES:
            self._show_error(f'"{name}" is a built-in theme and cannot be overwritten.')
            return
        if name in THEMES:
            # Custom theme with this name already exists — confirm overwrite.
            reply = QMessageBox.question(
                self, "Overwrite?",
                f'A custom theme named "{name}" already exists.\nOverwrite it?',
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._tm.save_custom_theme(name, dict(self._palette))
        self._cleaned_up = True   # theme is already applied; don't restore on close
        self.close()

    def _cancel(self) -> None:
        self._do_restore()
        self.close()

    def _do_restore(self) -> None:
        if not self._cleaned_up:
            self._cleaned_up = True
            self._tm.apply_theme(self._restore_name)

    def _show_error(self, msg: str) -> None:
        self._err_label.setText(msg)
        self._err_label.show()

    # ──────────────────────────────────────────────────────────────────
    # Qt overrides
    # ──────────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._do_restore()
        super().closeEvent(event)
