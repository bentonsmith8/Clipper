"""
Shared pytest fixtures and environment setup for all Clipper tests.
"""

import os
import sys

# Use Qt's offscreen platform so tests run without a display / GUI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the project root importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication instance shared across the whole test session."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


@pytest.fixture
def clean_custom_themes():
    """
    Ensure that any custom themes written to THEMES / QSettings during a test
    are cleaned up afterwards, so tests don't bleed state into each other.
    """
    import json
    from PyQt6.QtCore import QSettings
    from core.constants import SERVICE_NAME
    from ui.themes import THEMES, BUILTIN_THEME_NAMES

    yield  # ← run the test

    # Remove custom entries added to the module-level dict.
    for key in list(THEMES.keys()):
        if key not in BUILTIN_THEME_NAMES:
            del THEMES[key]

    # Wipe custom-theme QSettings entries.
    s = QSettings(SERVICE_NAME, SERVICE_NAME)
    names = json.loads(s.value("custom_theme_names", "[]"))
    for name in names:
        s.remove(f"custom_themes/{name}")
    s.setValue("custom_theme_names", "[]")
    s.sync()
