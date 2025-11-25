"""Entry point for the VibePlaylist AI desktop application."""

from __future__ import annotations

import logging
import sys

from PyQt5 import QtWidgets

from vibeplaylist.gui.interface import MainWindow
from vibeplaylist.utils import setup_logging


def main() -> None:
    """Launch the Qt application."""

    setup_logging(logging.INFO)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
