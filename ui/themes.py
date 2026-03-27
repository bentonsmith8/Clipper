"""
ui/themes.py
Theme management — colour palettes and QSS generation.
"""

from __future__ import annotations
import json
import os
from string import Template

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from core.constants import SERVICE_NAME


# ──────────────────────────────────────────────────────────────────────────────
# Palette definitions
# Each palette supplies exactly the keys referenced in style_template.qss.
# ──────────────────────────────────────────────────────────────────────────────

THEMES: dict[str, dict[str, str]] = {

    "Dark Industrial": {
        # backgrounds (darkest → lightest)
        "bg_deepest":      "#090914",  # log viewer, status bar
        "bg_base":         "#0f0f1a",  # main window
        "bg_surface":      "#12121f",  # controls bar, timeline
        "bg_elevated":     "#14142a",  # menu dropdowns
        "bg_input":        "#1a1a2e",  # text inputs, combo boxes
        "bg_io":           "#1e1e34",  # IO buttons
        "bg_button":       "#2a2a3e",  # general buttons / default borders
        "bg_button_hover": "#3a3a5a",  # button hover / strong border
        "bg_group":        "#11111e",  # group box fill
        "bg_menu":         "#0d0d18",  # menu bar, export panel header
        "bg_selected":     "#2a2a4a",  # selection highlight
        # accent
        "accent":          "#00d4aa",
        "accent_bright":   "#00ffcc",
        "accent_dim":      "#00a888",
        "accent_bg":       "#003d2e",  # subtle accent-tinted bg
        # danger
        "danger":          "#ff6b6b",
        "danger_bg":       "#3a1a1a",
        # IO / tooltip borders
        "border_io":       "#3d5a80",
        "border_io_dim":   "#2d4a70",
        # text
        "text_primary":    "#c8c8d8",
        "text_secondary":  "#8a8aaa",
        "text_muted":      "#5a5a7a",
        "text_faint":      "#4a4a6a",
        "text_log":        "#6a8a6a",
    },

    "Desert": {
        "bg_deepest":      "#c8b85c",
        "bg_base":         "#e8dc98",
        "bg_surface":      "#ddd08a",
        "bg_elevated":     "#f4edb8",
        "bg_input":        "#faf6d8",
        "bg_io":           "#e8d888",
        "bg_button":       "#caba68",
        "bg_button_hover": "#b8a850",
        "bg_group":        "#ede4a8",
        "bg_menu":         "#d8cc80",
        "bg_selected":     "#f0c840",
        "accent":          "#6a4008",
        "accent_bright":   "#8a5810",
        "accent_dim":      "#502e04",
        "accent_bg":       "#f0dc98",
        "danger":          "#b82010",
        "danger_bg":       "#f8d0c8",
        "border_io":       "#8a6010",
        "border_io_dim":   "#6a4808",
        "text_primary":    "#1e1204",
        "text_secondary":  "#4a3010",
        "text_muted":      "#7a5828",
        "text_faint":      "#9a7840",
        "text_log":        "#185010",
    },

    "Bronze": {
        "bg_deepest":      "#251c0e",
        "bg_base":         "#2e2212",
        "bg_surface":      "#382a18",
        "bg_elevated":     "#443220",
        "bg_input":        "#503c28",
        "bg_io":           "#5a4430",
        "bg_button":       "#6a5238",
        "bg_button_hover": "#7e6448",
        "bg_group":        "#3a2a18",
        "bg_menu":         "#281e0e",
        "bg_selected":     "#6a5038",
        "accent":          "#f0b050",
        "accent_bright":   "#ffc860",
        "accent_dim":      "#d09038",
        "accent_bg":       "#5a3800",
        "danger":          "#e86060",
        "danger_bg":       "#502020",
        "border_io":       "#a07840",
        "border_io_dim":   "#806030",
        "text_primary":    "#f0e0c0",
        "text_secondary":  "#c8b888",
        "text_muted":      "#a09060",
        "text_faint":      "#806840",
        "text_log":        "#a0c068",
    },

    "Ocean": {
        "bg_deepest":      "#020816",
        "bg_base":         "#04102a",
        "bg_surface":      "#061535",
        "bg_elevated":     "#081c42",
        "bg_input":        "#0d2655",
        "bg_io":           "#102d60",
        "bg_button":       "#183a70",
        "bg_button_hover": "#244a88",
        "bg_group":        "#061230",
        "bg_menu":         "#030c1e",
        "bg_selected":     "#1a3a70",
        "accent":          "#00c8f0",
        "accent_bright":   "#40dcff",
        "accent_dim":      "#00a0c0",
        "accent_bg":       "#00304a",
        "danger":          "#ff5c7a",
        "danger_bg":       "#3a101e",
        "border_io":       "#2860a0",
        "border_io_dim":   "#1e4880",
        "text_primary":    "#c0d8f0",
        "text_secondary":  "#7090b8",
        "text_muted":      "#4a6888",
        "text_faint":      "#304a68",
        "text_log":        "#50a880",
    },

    "Light": {
        "bg_deepest":      "#d8d8e0",
        "bg_base":         "#f0f0f5",
        "bg_surface":      "#e8e8f0",
        "bg_elevated":     "#ffffff",
        "bg_input":        "#ffffff",
        "bg_io":           "#e0e8f5",
        "bg_button":       "#d0d0dc",
        "bg_button_hover": "#b8b8cc",
        "bg_group":        "#ebebf3",
        "bg_menu":         "#e4e4ec",
        "bg_selected":     "#c8d8f0",
        "accent":          "#0077cc",
        "accent_bright":   "#0099ff",
        "accent_dim":      "#005599",
        "accent_bg":       "#d0e8ff",
        "danger":          "#cc3333",
        "danger_bg":       "#ffe0e0",
        "border_io":       "#4488cc",
        "border_io_dim":   "#2266aa",
        "text_primary":    "#1a1a2a",
        "text_secondary":  "#4a4a60",
        "text_muted":      "#707088",
        "text_faint":      "#909090",
        "text_log":        "#2a6a2a",
    },

    "Forest": {
        "bg_deepest":      "#040a04",
        "bg_base":         "#0a1208",
        "bg_surface":      "#0f1a0c",
        "bg_elevated":     "#142012",
        "bg_input":        "#1a2a18",
        "bg_io":           "#1e3020",
        "bg_button":       "#2a3c28",
        "bg_button_hover": "#384e34",
        "bg_group":        "#0d1a0b",
        "bg_menu":         "#070f06",
        "bg_selected":     "#2a3c28",
        "accent":          "#5ab864",
        "accent_bright":   "#72d080",
        "accent_dim":      "#409848",
        "accent_bg":       "#0a2c0e",
        "danger":          "#cc5044",
        "danger_bg":       "#2c1010",
        "border_io":       "#3a7840",
        "border_io_dim":   "#286030",
        "text_primary":    "#c8d8c0",
        "text_secondary":  "#88a880",
        "text_muted":      "#587850",
        "text_faint":      "#3a5835",
        "text_log":        "#78b858",
    },

    "Neon": {
        "bg_deepest":      "#020205",
        "bg_base":         "#08080f",
        "bg_surface":      "#0d0d18",
        "bg_elevated":     "#111122",
        "bg_input":        "#161630",
        "bg_io":           "#1a1a38",
        "bg_button":       "#221a40",
        "bg_button_hover": "#302855",
        "bg_group":        "#0d0d1e",
        "bg_menu":         "#060610",
        "bg_selected":     "#221a48",
        "accent":          "#ff00ff",
        "accent_bright":   "#ff55ff",
        "accent_dim":      "#cc00cc",
        "accent_bg":       "#300030",
        "danger":          "#ff3333",
        "danger_bg":       "#330000",
        "border_io":       "#7700cc",
        "border_io_dim":   "#550099",
        "text_primary":    "#e8e0ff",
        "text_secondary":  "#a888cc",
        "text_muted":      "#6a50a0",
        "text_faint":      "#4a3878",
        "text_log":        "#00ff88",
    },
}

THEME_NAMES: list[str] = list(THEMES.keys())
DEFAULT_THEME = "Dark Industrial"

# Snapshot of built-in names so custom themes can never overwrite them.
BUILTIN_THEME_NAMES: frozenset[str] = frozenset(THEME_NAMES)

# ──────────────────────────────────────────────────────────────────────────────
# QSS generation
# ──────────────────────────────────────────────────────────────────────────────

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "style_template.qss")


def build_stylesheet_from_palette(palette: dict) -> str:
    """Return a fully-substituted QSS string for an arbitrary palette dict."""
    with open(_TEMPLATE_PATH, "r") as f:
        return Template(f.read()).substitute(palette)


def build_stylesheet(theme_name: str) -> str:
    """Return a fully-substituted QSS string for the given named theme."""
    return build_stylesheet_from_palette(THEMES[theme_name])


# ──────────────────────────────────────────────────────────────────────────────
# ThemeManager — app-level singleton
# ──────────────────────────────────────────────────────────────────────────────

class ThemeManager(QObject):
    """Manages theme selection, stylesheet application, and persistence."""

    # Emitted after any theme/palette is applied: (theme_name, palette_dict).
    # theme_name is "" during live preview so listeners can skip checkmark updates.
    theme_changed = pyqtSignal(str, dict)

    # Emitted when the list of custom themes changes (theme added/deleted).
    custom_themes_changed = pyqtSignal(list)  # list of custom theme name strings

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._custom_names: list[str] = []
        self._load_custom_themes()
        settings = QSettings(SERVICE_NAME, SERVICE_NAME)
        saved = settings.value("theme", DEFAULT_THEME)
        self._current = saved if saved in THEMES else DEFAULT_THEME

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_theme(self) -> str:
        return self._current

    @property
    def palette(self) -> dict:
        return THEMES[self._current]

    @property
    def custom_theme_names(self) -> list[str]:
        return list(self._custom_names)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def apply_theme(self, theme_name: str) -> None:
        """Switch to *theme_name*, update the stylesheet, and persist."""
        if theme_name not in THEMES:
            return
        self._current = theme_name
        self._app.setStyleSheet(build_stylesheet(theme_name))
        QSettings(SERVICE_NAME, SERVICE_NAME).setValue("theme", theme_name)
        self.theme_changed.emit(theme_name, THEMES[theme_name])

    def apply_palette(self, palette: dict) -> None:
        """Apply a raw palette dict for live preview without persisting."""
        self._app.setStyleSheet(build_stylesheet_from_palette(palette))
        self.theme_changed.emit("", palette)

    def save_custom_theme(self, name: str, palette: dict) -> None:
        """Persist a custom theme, register it, and switch to it."""
        if name in BUILTIN_THEME_NAMES:
            raise ValueError(f"'{name}' is a built-in theme name")
        THEMES[name] = dict(palette)
        if name not in self._custom_names:
            self._custom_names.append(name)
        settings = QSettings(SERVICE_NAME, SERVICE_NAME)
        settings.setValue("custom_theme_names", json.dumps(self._custom_names))
        settings.setValue(f"custom_themes/{name}", json.dumps(palette))
        self._current = name
        settings.setValue("theme", name)
        self._app.setStyleSheet(build_stylesheet_from_palette(palette))
        self.theme_changed.emit(name, palette)
        self.custom_themes_changed.emit(list(self._custom_names))

    def apply_saved(self) -> None:
        """Apply the theme that was persisted from the last session."""
        self.apply_theme(self._current)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_custom_themes(self) -> None:
        settings = QSettings(SERVICE_NAME, SERVICE_NAME)
        names = json.loads(settings.value("custom_theme_names", "[]"))
        for name in names:
            raw = settings.value(f"custom_themes/{name}", None)
            if raw:
                try:
                    palette = json.loads(raw)
                    THEMES[name] = palette
                    self._custom_names.append(name)
                except (json.JSONDecodeError, KeyError):
                    pass
