import json
from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..mood_analyzer import analyze_text
from ..playlist_namer import generate_playlist_name
from ..utils import ensure_config_dir, get_logger
from ..yandex_client import create_playlist, init_client, search_tracks

logger = get_logger(__name__)


class TokenDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Введите токен Яндекс Музыки")
        self.token_input = QLineEdit(self)
        self.token_input.setEchoMode(QLineEdit.Password)
        layout = QFormLayout(self)
        layout.addRow(QLabel("OAuth токен:"), self.token_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_token(self) -> str:
        if self.exec_() == QDialog.Accepted:
            return self.token_input.text().strip()
        return ""


class VibePlaylistApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VibePlaylist AI")
        self.setMinimumWidth(600)
        self.token_path = ensure_config_dir() / "token.json"
        self.token = self.load_or_request_token()
        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        layout = QVBoxLayout()

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Опишите ваш вайб")
        layout.addWidget(self.text_input)

        self.generate_button = QPushButton("Создать плейлист")
        self.generate_button.clicked.connect(self.handle_generate)
        layout.addWidget(self.generate_button)

        self.tracks_list = QListWidget()
        layout.addWidget(self.tracks_list)

        self.save_button = QPushButton("Сохранить плейлист в Яндекс Музыке")
        self.save_button.clicked.connect(self.handle_save_playlist)
        layout.addWidget(self.save_button)

        self.status_label = QLabel("Готово")
        layout.addWidget(self.status_label)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def load_or_request_token(self) -> str:
        if self.token_path.exists():
            try:
                data = json.loads(self.token_path.read_text(encoding="utf-8"))
                token = data.get("token", "")
                if token:
                    init_client(token)
                    return token
            except json.JSONDecodeError:
                logger.error("Не удалось прочитать token.json")

        dialog = TokenDialog(self)
        token = dialog.get_token()
        if not token:
            QMessageBox.critical(self, "Ошибка", "Необходимо ввести токен для продолжения")
            raise SystemExit(1)
        self.save_token(token)
        init_client(token)
        return token

    def save_token(self, token: str):
        payload = {"token": token}
        self.token_path.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("Token saved to %s", self.token_path)

    def handle_generate(self):
        description = self.text_input.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "Пустое описание", "Пожалуйста, опишите ваш вайб")
            return
        try:
            analysis = analyze_text(description)
            tracks = search_tracks(
                analysis.get("genres", []),
                analysis.get("moods", []),
                analysis.get("keywords", []),
            )
            self.display_tracks(tracks)
            self.current_tracks = tracks
            self.current_analysis = analysis
            self.status_label.setText(f"Найдено треков: {len(tracks)}")
            logger.info("Generated playlist candidates: %d tracks", len(tracks))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при поиске треков: %s", exc)
            QMessageBox.critical(self, "Ошибка", f"Не удалось найти треки: {exc}")

    def display_tracks(self, tracks: List):
        self.tracks_list.clear()
        for track in tracks:
            artists = ", ".join(artist.name for artist in track.artists) if track.artists else ""
            item = QListWidgetItem(f"{track.title} — {artists}")
            item.setData(Qt.UserRole, track)
            self.tracks_list.addItem(item)

    def handle_save_playlist(self):
        tracks = getattr(self, "current_tracks", [])
        analysis = getattr(self, "current_analysis", {"moods": [], "genres": [], "keywords": []})
        if not tracks:
            QMessageBox.warning(self, "Нет треков", "Сначала сгенерируйте треки")
            return
        title = generate_playlist_name(
            analysis.get("moods", []),
            analysis.get("genres", []),
            analysis.get("keywords", []),
        )
        try:
            result = create_playlist(title, tracks)
            self.status_label.setText(f"Плейлист '{result['title']}' сохранен")
            logger.info("Playlist created: %s", result)
            QMessageBox.information(self, "Успех", f"Плейлист '{title}' сохранен в Яндекс Музыке")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при создании плейлиста: %s", exc)
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить плейлист: {exc}")
