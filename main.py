"""
VideoForge - Video Trimmer & Exporter
Entry point for the application.
"""

import sys
import os

# Ensure the app directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow


def main():
    # Enable high DPI scaling
    app = QApplication(sys.argv)
    app.setApplicationName("Clipper")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Clipper")

    # Apply global stylesheet
    with open(os.path.join(os.path.dirname(__file__), "ui", "style.qss"), "r") as f:
        app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
