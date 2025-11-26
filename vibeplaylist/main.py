import sys

from PyQt5.QtWidgets import QApplication

from .gui.interface import VibePlaylistApp
from .utils import configure_logging, get_logger


def run_app():
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Starting VibePlaylist AI")
    app = QApplication(sys.argv)
    window = VibePlaylistApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_app()
