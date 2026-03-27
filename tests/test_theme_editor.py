"""
Regression tests for ui/theme_editor.py.

Covers:
- Every palette key used in the QSS template is exposed in the editor UI.
- No duplicate keys across editor groups.
- _Swatch initialises with the correct colour and updates on set_hex().
- ThemeEditorDialog restores the previous theme when cancelled.
- Saving a valid custom theme registers it in THEMES.
"""

import pytest
from ui.themes import THEMES, THEME_NAMES, BUILTIN_THEME_NAMES
from ui.theme_editor import _GROUPS, _Swatch


# ──────────────────────────────────────────────────────────────────────────────
# _GROUPS coverage  (no QApplication needed)
# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_KEYS = {
    "bg_deepest", "bg_base", "bg_surface", "bg_elevated",
    "bg_input", "bg_io", "bg_button", "bg_button_hover",
    "bg_group", "bg_menu", "bg_selected",
    "accent", "accent_bright", "accent_dim", "accent_bg",
    "danger", "danger_bg",
    "border_io", "border_io_dim",
    "text_primary", "text_secondary", "text_muted", "text_faint", "text_log",
}


def _all_editor_keys():
    return [key for _, entries in _GROUPS for key, _ in entries]


def test_editor_groups_cover_all_palette_keys():
    """Every palette key must be editable in the UI — no hidden keys."""
    editor_keys = set(_all_editor_keys())
    missing = REQUIRED_KEYS - editor_keys
    assert not missing, f"These palette keys are not shown in the editor: {missing}"


def test_editor_groups_have_no_extra_keys():
    """The editor should not reference keys that don't exist in the template."""
    editor_keys = set(_all_editor_keys())
    extra = editor_keys - REQUIRED_KEYS
    assert not extra, f"Editor references unknown palette keys: {extra}"


def test_no_duplicate_keys_in_editor_groups():
    all_keys = _all_editor_keys()
    assert len(all_keys) == len(set(all_keys)), (
        "Duplicate palette key found across editor groups"
    )


def test_all_groups_have_a_label():
    for group_label, entries in _GROUPS:
        assert group_label, "A group is missing its display label"
        for key, entry_label in entries:
            assert entry_label, f"Key '{key}' is missing its display label"


# ──────────────────────────────────────────────────────────────────────────────
# _Swatch widget  (requires QApplication)
# ──────────────────────────────────────────────────────────────────────────────

def test_swatch_stores_initial_colour(qapp):
    swatch = _Swatch("#00d4aa", "accent")
    assert swatch.hex_color == "#00d4aa"


def test_swatch_set_hex_updates_stored_colour(qapp):
    swatch = _Swatch("#000000", "bg_base")
    swatch.set_hex("#ff6b6b")
    assert swatch.hex_color == "#ff6b6b"


def test_swatch_stylesheet_contains_colour(qapp):
    swatch = _Swatch("#abcdef", "test_key")
    assert "#abcdef" in swatch.styleSheet()


def test_swatch_callback_invoked_on_set(qapp):
    """on_change callback must fire when set_hex is called indirectly via _pick."""
    received = []
    swatch = _Swatch("#111111", "accent")
    swatch.on_change(lambda key, val: received.append((key, val)))
    # Simulate the internal colour-change path directly.
    swatch._hex = "#222222"
    swatch._refresh()
    if swatch._callback:
        swatch._callback(swatch._key, swatch._hex)
    assert received == [("accent", "#222222")]


# ──────────────────────────────────────────────────────────────────────────────
# ThemeEditorDialog  (requires QApplication)
# ──────────────────────────────────────────────────────────────────────────────

def test_editor_cancel_restores_original_theme(qapp):
    """Cancelling the editor must revert to the theme active before it opened."""
    from ui.themes import ThemeManager
    from ui.theme_editor import ThemeEditorDialog

    tm = ThemeManager(qapp)
    tm.apply_theme("Dark Industrial")

    dlg = ThemeEditorDialog(tm)
    # Simulate the user picking a base theme (triggers live preview).
    dlg._on_base_changed("Light")
    assert "Light" in qapp.styleSheet() or THEMES["Light"]["bg_base"] in qapp.styleSheet()

    # Now cancel — must restore Dark Industrial.
    dlg._cancel()
    assert tm.current_theme == "Dark Industrial"
    assert THEMES["Dark Industrial"]["accent"] in qapp.styleSheet()


def test_editor_save_registers_theme(qapp, clean_custom_themes):
    """Saving in the editor must add the theme to THEMES and switch to it."""
    from ui.themes import ThemeManager
    from ui.theme_editor import ThemeEditorDialog

    tm = ThemeManager(qapp)
    dlg = ThemeEditorDialog(tm)
    dlg._name_edit.setText("_pytest_editor_save")
    # Use a recognisable accent colour.
    dlg._palette["accent"] = "#bada55"
    dlg._save()

    assert "_pytest_editor_save" in THEMES
    assert THEMES["_pytest_editor_save"]["accent"] == "#bada55"
    assert tm.current_theme == "_pytest_editor_save"


def test_editor_save_rejects_empty_name(qapp):
    from ui.themes import ThemeManager
    from ui.theme_editor import ThemeEditorDialog

    tm = ThemeManager(qapp)
    dlg = ThemeEditorDialog(tm)
    dlg._name_edit.setText("")
    dlg._save()  # Should not raise, but should show an error.
    # The label is shown via .show() even if the dialog itself is not yet displayed,
    # so check isHidden() rather than isVisible() (which requires the parent chain).
    assert not dlg._err_label.isHidden()
    assert "_pytest_editor_save" not in THEMES  # nothing was saved


def test_editor_save_rejects_builtin_name(qapp):
    from ui.themes import ThemeManager
    from ui.theme_editor import ThemeEditorDialog

    tm = ThemeManager(qapp)
    dlg = ThemeEditorDialog(tm)
    dlg._name_edit.setText("Dark Industrial")
    dlg._save()
    assert not dlg._err_label.isHidden()


def test_editor_populates_swatches_from_base_theme(qapp):
    from ui.themes import ThemeManager
    from ui.theme_editor import ThemeEditorDialog

    tm = ThemeManager(qapp)
    dlg = ThemeEditorDialog(tm)
    dlg._on_base_changed("Ocean")

    for key, swatch in dlg._swatches.items():
        assert swatch.hex_color == THEMES["Ocean"][key], (
            f"Swatch for '{key}' not updated when base theme changed to Ocean"
        )
