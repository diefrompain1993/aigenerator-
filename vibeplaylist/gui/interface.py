"""PyQt interface for the VibePlaylist AI application."""

from __future__ import annotations

import logging
import threading
from typing import List

from PyQt5 import QtCore, QtWidgets

from vibeplaylist import mood_analyzer, playlist_namer, yandex_client
from vibeplaylist.utils import cache_token, resolve_token

logger = logging.getLogger(__name__)


class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)


class SearchWorker(threading.Thread):
    def __init__(self, text: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text = text
        self.signals = WorkerSignals()

    def run(self) -> None:  # pragma: no cover - threaded
        try:
            analysis = mood_analyzer.analyze_text(self.text)
            tracks = yandex_client.search_tracks(
                analysis["genres"], analysis["moods"], analysis["keywords"]
            )
            self.signals.finished.emit(tracks)
        except Exception as error:  # pragma: no cover - network
            logger.exception("Search failed: %s", error)
            self.signals.error.emit(str(error))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VibePlaylist AI")
        self.resize(800, 600)
        self._init_ui()
        self._init_token()

    def _init_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        self.status_label = QtWidgets.QLabel("Введите описание вайба и нажмите 'Создать плейлист'")
        self.vibe_input = QtWidgets.QTextEdit()
        self.vibe_input.setPlaceholderText("Например: 'Ночной ретро синтвейв с космическим настроением'")

        self.token_input = QtWidgets.QLineEdit()
        self.token_input.setPlaceholderText("Токен Yandex Music")

        self.create_button = QtWidgets.QPushButton("Создать плейлист")
        self.create_button.clicked.connect(self.handle_create_playlist)

        self.track_list = QtWidgets.QListWidget()

        self.save_button = QtWidgets.QPushButton("Сохранить плейлист в Яндекс Музыке")
        self.save_button.clicked.connect(self.handle_save_playlist)
        self.save_button.setEnabled(False)

        layout.addWidget(self.status_label)
        layout.addWidget(self.vibe_input)
        layout.addWidget(self.token_input)
        layout.addWidget(self.create_button)
        layout.addWidget(self.track_list)
        layout.addWidget(self.save_button)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _init_token(self) -> None:
        token = resolve_token()
        if token:
            self.token_input.setText(token)
            try:
                yandex_client.init_client(token)
                self.status_label.setText("Клиент Яндекс Музыки готов")
            except Exception as error:  # pragma: no cover - network
                logger.exception("Failed to initialize client: %s", error)
                self._show_error(f"Ошибка инициализации клиента: {error}")

    def handle_create_playlist(self) -> None:
        text = self.vibe_input.toPlainText()
        token = self.token_input.text().strip()
        if not text:
            self._show_warning("Введите описание вайба")
            return
        if not token:
            self._show_warning("Укажите токен Яндекс Музыки")
            return
        try:
            yandex_client.init_client(token)
            cache_token(token)
        except Exception as error:  # pragma: no cover - network
            self._show_error(f"Неверный токен: {error}")
            return

        self.status_label.setText("Поиск треков...")
        self.create_button.setEnabled(False)
        worker = SearchWorker(text)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.error.connect(self._on_search_error)
        worker.start()
        self._worker = worker

    def _on_search_finished(self, tracks: List[dict]) -> None:
        self.track_list.clear()
        if not tracks:
            self.status_label.setText("Ничего не найдено")
            self.save_button.setEnabled(False)
            return

        for track in tracks:
            item = QtWidgets.QListWidgetItem(f"{track['artist']} — {track['title']}")
            item.setData(QtCore.Qt.UserRole, track)
            self.track_list.addItem(item)
        self.status_label.setText("Треки найдены. Проверьте список перед сохранением.")
        self.save_button.setEnabled(True)
        self.create_button.setEnabled(True)

    def _on_search_error(self, message: str) -> None:
        self._show_error(message)
        self.create_button.setEnabled(True)

    def handle_save_playlist(self) -> None:
        tracks = [self.track_list.item(i).data(QtCore.Qt.UserRole) for i in range(self.track_list.count())]
        if not tracks:
            self._show_warning("Сначала выполните поиск треков")
            return
        analysis = mood_analyzer.analyze_text(self.vibe_input.toPlainText())
        title = playlist_namer.generate_playlist_name(
            analysis["moods"], analysis["genres"], analysis["keywords"]
        )
        try:
            info = yandex_client.create_playlist(title, tracks)
            self.status_label.setText(f"Плейлист '{info['title']}' создан")
            QtWidgets.QMessageBox.information(self, "Успех", "Плейлист сохранен в аккаунте")
        except Exception as error:  # pragma: no cover - network
            self._show_error(f"Не удалось создать плейлист: {error}")

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        QtWidgets.QMessageBox.critical(self, "Ошибка", message)

    def _show_warning(self, message: str) -> None:
        self.status_label.setText(message)
        QtWidgets.QMessageBox.warning(self, "Предупреждение", message)


__all__ = ["MainWindow"]
