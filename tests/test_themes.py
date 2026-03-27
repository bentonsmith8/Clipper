"""
Regression tests for the theme system (ui/themes.py).

Covers:
- Every built-in palette has all 24 required keys with valid hex values.
- QSS template substitution leaves no unresolved placeholders.
- ThemeManager correctly applies, persists, and restores themes.
- Custom theme save/reload round-trips cleanly.
"""

import re
import json
import pytest

from ui.themes import (
    THEMES,
    THEME_NAMES,
    BUILTIN_THEME_NAMES,
    DEFAULT_THEME,
    build_stylesheet,
    build_stylesheet_from_palette,
)

# The exact set of keys the QSS template expects.
REQUIRED_KEYS = {
    "bg_deepest", "bg_base", "bg_surface", "bg_elevated",
    "bg_input", "bg_io", "bg_button", "bg_button_hover",
    "bg_group", "bg_menu", "bg_selected",
    "accent", "accent_bright", "accent_dim", "accent_bg",
    "danger", "danger_bg",
    "border_io", "border_io_dim",
    "text_primary", "text_secondary", "text_muted", "text_faint", "text_log",
}

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


# ──────────────────────────────────────────────────────────────────────────────
# Palette completeness & validity  (no QApplication needed)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("theme_name", THEME_NAMES)
def test_palette_has_all_required_keys(theme_name):
    missing = REQUIRED_KEYS - set(THEMES[theme_name].keys())
    assert not missing, f"'{theme_name}' is missing palette keys: {missing}"


@pytest.mark.parametrize("theme_name", THEME_NAMES)
def test_palette_values_are_valid_hex(theme_name):
    for key, value in THEMES[theme_name].items():
        assert HEX_RE.match(value), (
            f"'{theme_name}.{key}' = {value!r} is not a valid #rrggbb hex colour"
        )


def test_no_duplicate_theme_names():
    assert len(THEME_NAMES) == len(set(THEME_NAMES))


def test_default_theme_exists():
    assert DEFAULT_THEME in THEMES


def test_builtin_theme_names_is_frozenset_of_originals():
    assert isinstance(BUILTIN_THEME_NAMES, frozenset)
    assert BUILTIN_THEME_NAMES == frozenset(THEME_NAMES)


# ──────────────────────────────────────────────────────────────────────────────
# QSS generation  (no QApplication needed)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("theme_name", THEME_NAMES)
def test_stylesheet_has_no_unresolved_placeholders(theme_name):
    css = build_stylesheet(theme_name)
    assert "${" not in css, f"Unresolved ${{...}} in stylesheet for '{theme_name}'"


@pytest.mark.parametrize("theme_name", THEME_NAMES)
def test_stylesheet_is_non_trivially_long(theme_name):
    # A fully substituted stylesheet should be several kilobytes.
    css = build_stylesheet(theme_name)
    assert len(css) > 2_000, f"Stylesheet for '{theme_name}' is suspiciously short"


@pytest.mark.parametrize("theme_name", THEME_NAMES)
def test_stylesheet_contains_accent_colour(theme_name):
    # The accent colour must appear somewhere in the rendered CSS.
    accent = THEMES[theme_name]["accent"]
    css = build_stylesheet(theme_name)
    assert accent in css, (
        f"Accent colour {accent} not found in stylesheet for '{theme_name}'"
    )


def test_build_stylesheet_from_palette_matches_named():
    """build_stylesheet(name) and build_stylesheet_from_palette(dict) must agree."""
    for name in THEME_NAMES:
        assert build_stylesheet(name) == build_stylesheet_from_palette(THEMES[name])


def test_all_palette_keys_referenced_in_template():
    """Every palette key should appear in the QSS template (no dead keys)."""
    import os
    from string import Template
    tpl_path = os.path.join(os.path.dirname(__file__), "..", "ui", "style_template.qss")
    with open(tpl_path) as f:
        content = f.read()
    template_keys = set(re.findall(r"\$\{(\w+)\}", content))
    assert template_keys == REQUIRED_KEYS


# ──────────────────────────────────────────────────────────────────────────────
# ThemeManager  (requires QApplication)
# ──────────────────────────────────────────────────────────────────────────────

class TestThemeManager:

    def test_init_falls_back_to_default_when_no_saved_setting(self, qapp):
        from PyQt6.QtCore import QSettings
        from core.constants import SERVICE_NAME
        from ui.themes import ThemeManager
        s = QSettings(SERVICE_NAME, SERVICE_NAME)
        s.remove("theme")
        s.sync()
        tm = ThemeManager(qapp)
        assert tm.current_theme == DEFAULT_THEME

    def test_apply_theme_updates_current_theme(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        for name in THEME_NAMES:
            tm.apply_theme(name)
            assert tm.current_theme == name

    def test_apply_theme_injects_accent_into_stylesheet(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        for name in THEME_NAMES:
            tm.apply_theme(name)
            assert THEMES[name]["accent"] in qapp.styleSheet(), (
                f"Accent for '{name}' not found in app stylesheet"
            )

    def test_apply_invalid_theme_name_is_noop(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        tm.apply_theme("Dark Industrial")
        tm.apply_theme("__nonexistent_theme__")
        assert tm.current_theme == "Dark Industrial"

    def test_apply_palette_changes_stylesheet_without_updating_current_theme(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        tm.apply_theme("Dark Industrial")

        preview = dict(THEMES["Dark Industrial"])
        preview["bg_base"] = "#cafe00"
        tm.apply_palette(preview)

        assert "#cafe00" in qapp.styleSheet()
        # current_theme must not change during a live preview
        assert tm.current_theme == "Dark Industrial"

    def test_theme_changed_signal_emitted_on_apply(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        received = []
        tm.theme_changed.connect(lambda name, pal: received.append((name, pal)))
        tm.apply_theme("Ocean")
        assert len(received) == 1
        assert received[0][0] == "Ocean"
        assert received[0][1] == THEMES["Ocean"]

    def test_apply_palette_emits_empty_name_signal(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        received = []
        tm.theme_changed.connect(lambda name, pal: received.append(name))
        tm.apply_palette(dict(THEMES["Light"]))
        assert received == [""]

    def test_save_custom_theme_roundtrip(self, qapp, clean_custom_themes):
        from ui.themes import ThemeManager, THEMES, BUILTIN_THEME_NAMES
        custom_palette = dict(THEMES["Dark Industrial"])
        custom_palette["accent"] = "#112233"
        name = "_pytest_custom_alpha"

        tm = ThemeManager(qapp)
        tm.save_custom_theme(name, custom_palette)

        assert name in THEMES
        assert name not in BUILTIN_THEME_NAMES
        assert tm.current_theme == name
        assert THEMES[name]["accent"] == "#112233"

        # Simulate a fresh startup — a new ThemeManager should reload the theme.
        tm2 = ThemeManager(qapp)
        assert name in THEMES
        assert THEMES[name]["accent"] == "#112233"

    def test_save_custom_theme_emits_custom_themes_changed(self, qapp, clean_custom_themes):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        received = []
        tm.custom_themes_changed.connect(received.append)
        tm.save_custom_theme("_pytest_custom_beta", dict(THEMES["Light"]))
        assert received == [["_pytest_custom_beta"]]

    def test_save_custom_theme_rejects_builtin_name(self, qapp):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        with pytest.raises(ValueError, match="built-in"):
            tm.save_custom_theme("Dark Industrial", dict(THEMES["Dark Industrial"]))

    def test_custom_theme_names_property(self, qapp, clean_custom_themes):
        from ui.themes import ThemeManager
        tm = ThemeManager(qapp)
        assert "_pytest_custom_gamma" not in tm.custom_theme_names
        tm.save_custom_theme("_pytest_custom_gamma", dict(THEMES["Forest"]))
        assert "_pytest_custom_gamma" in tm.custom_theme_names
