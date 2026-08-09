"""
app_controller.py
=================
Coordinates the two-window architecture for cqli, modelled after qchess's
ApplicationController.

Communication flow:
    ChessCQLiApp (main window) ── emits ──► gameSelected(dict)
    AppController ──► ChessAppWindow.load_game(dict)
"""

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon

from gui.chess_app import ChessAppWindow


class AppController(QObject):
    """Manages the lifecycle of ChessAppWindow.

    Responsibilities:
    - Creates and reuses a single ``ChessAppWindow`` instance (lazy-created
      on first game selection, mirroring qchess behaviour).
    - Routes ``gameSelected`` signals from ``ChessCQLiApp`` to the window.
    - Keeps the window alive between games (hide/show) to avoid re-creating
      the engine and all widgets repeatedly.
    """

    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self._main_app = main_app  # ChessCQLiApp instance
        self._window: ChessAppWindow | None = None  # lazy-created

        # Wire signals from the main CQLi app
        main_app.gameSelected.connect(self._on_game_selected)

    # ──────────────────────── Signal Handlers ────────────────────────

    def _on_game_selected(self, game_data: dict):
        """Handle a game selection — open/reuse the ChessAppWindow."""
        window = self._get_or_create_window()
        window.load_game(game_data)
        window.show()
        window.raise_()
        window.activateWindow()

    # ──────────────────────── Window Management ────────────────────────

    def _get_or_create_window(self) -> ChessAppWindow:
        """Return the existing window or create a fresh one.

        Only one editor window is maintained at a time. If the window was
        fully destroyed (e.g. via task manager), a new one is created.
        """
        if self._window is None:
            self._window = ChessAppWindow()
            self._window.set_theme(self._main_app.dark_mode)
            icon = self._main_app.windowIcon()
            if not icon.isNull():
                self._window.setWindowIcon(icon)

        return self._window

    # ──────────────────────── Public API ────────────────────────

    def set_theme(self, is_dark: bool):
        """Propagate a theme change to the chess window if it exists."""
        if self._window is not None:
            self._window.set_theme(is_dark)

    def cleanup(self):
        """Explicitly destroy the window and its engine on application exit."""
        if self._window is not None:
            try:
                self._window.explorer.engine.quit()
            except Exception:
                pass
            self._window.deleteLater()
            self._window = None
