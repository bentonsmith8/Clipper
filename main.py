"""
Video Trimmer & Exporter
Entry point for the application.
"""

import sys
import os

# Ensure the app directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from core.constants import *
from ui.main_window import MainWindow
from ui.themes import ThemeManager


def main():
    # Enable high DPI scaling
    app = QApplication(sys.argv)
    app.setApplicationName(SERVICE_NAME)
    app.setApplicationVersion(SERVICE_VERSION)
    app.setOrganizationName(SERVICE_NAME)

    # Apply saved (or default) theme
    theme_manager = ThemeManager(app)
    theme_manager.apply_saved()

    window = MainWindow(theme_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
