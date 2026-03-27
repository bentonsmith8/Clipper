"""
Regression tests for ui/timeline_widget.py.

Covers:
- Default class-level colours stay in sync with the Dark Industrial palette.
- apply_theme() updates all eight colour instance variables correctly.
- In/out point and duration state behaves consistently.
"""

import pytest
from ui.themes import THEMES


# ──────────────────────────────────────────────────────────────────────────────
# Default colour constants  (no QApplication needed)
# ──────────────────────────────────────────────────────────────────────────────

def test_default_colors_match_dark_industrial_palette():
    """
    The class-level colour defaults in TimelineWidget must match the Dark
    Industrial theme so the widget looks correct before any theme is applied.
    """
    from ui.timeline_widget import TimelineWidget
    dark = THEMES["Dark Industrial"]

    assert TimelineWidget._C_BG         == dark["bg_input"]
    assert TimelineWidget._C_TRACK      == dark["bg_button"]
    assert TimelineWidget._C_RANGE_TOP  == dark["border_io"]
    assert TimelineWidget._C_RANGE_BOT  == dark["border_io_dim"]
    assert TimelineWidget._C_TICK_FAINT == dark["text_faint"]
    assert TimelineWidget._C_TICK_LABEL == dark["text_secondary"]
    assert TimelineWidget._C_HANDLE_IN  == dark["accent"]
    assert TimelineWidget._C_HANDLE_OUT == dark["danger"]


# ──────────────────────────────────────────────────────────────────────────────
# apply_theme()  (requires QApplication for widget instantiation)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("theme_name", list(THEMES.keys()))
def test_apply_theme_updates_all_color_attributes(qapp, theme_name):
    """apply_theme(palette) must update every painter colour attribute."""
    from ui.timeline_widget import TimelineWidget
    widget = TimelineWidget()
    palette = THEMES[theme_name]
    widget.apply_theme(palette)

    assert widget._C_BG         == palette["bg_input"]
    assert widget._C_TRACK      == palette["bg_button"]
    assert widget._C_RANGE_TOP  == palette["border_io"]
    assert widget._C_RANGE_BOT  == palette["border_io_dim"]
    assert widget._C_TICK_FAINT == palette["text_faint"]
    assert widget._C_TICK_LABEL == palette["text_secondary"]
    assert widget._C_HANDLE_IN  == palette["accent"]
    assert widget._C_HANDLE_OUT == palette["danger"]


def test_apply_theme_is_idempotent(qapp):
    """Applying the same theme twice should leave identical state."""
    from ui.timeline_widget import TimelineWidget
    widget = TimelineWidget()
    palette = THEMES["Ocean"]
    widget.apply_theme(palette)
    state_first = {k: getattr(widget, k) for k in
                   ("_C_BG", "_C_TRACK", "_C_RANGE_TOP", "_C_RANGE_BOT",
                    "_C_TICK_FAINT", "_C_TICK_LABEL", "_C_HANDLE_IN", "_C_HANDLE_OUT")}
    widget.apply_theme(palette)
    state_second = {k: getattr(widget, k) for k in state_first}
    assert state_first == state_second


# ──────────────────────────────────────────────────────────────────────────────
# In/out point & duration state  (requires QApplication)
# ──────────────────────────────────────────────────────────────────────────────

def test_initial_state(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    assert w._duration == 0.0
    assert w._in_point == 0.0
    assert w._out_point == 0.0
    assert w._position == 0.0


def test_set_duration(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    w.set_duration(120.0)
    assert w._duration == 120.0


def test_set_in_point_clamps_to_duration(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    w.set_duration(60.0)
    w.set_in_point(30.0)
    assert w._in_point == pytest.approx(30.0)


def test_set_out_point(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    w.set_duration(90.0)
    w.set_out_point(75.0)
    assert w._out_point == pytest.approx(75.0)


def test_reset_points_restores_full_range(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    w.set_duration(100.0)
    w.set_in_point(10.0)
    w.set_out_point(80.0)
    w.reset_points()
    assert w._in_point == 0.0
    assert w._out_point == pytest.approx(100.0)


def test_get_in_and_out_point(qapp):
    from ui.timeline_widget import TimelineWidget
    w = TimelineWidget()
    w.set_duration(50.0)
    w.set_in_point(5.0)
    w.set_out_point(45.0)
    assert w.get_in_point() == pytest.approx(5.0)
    assert w.get_out_point() == pytest.approx(45.0)
