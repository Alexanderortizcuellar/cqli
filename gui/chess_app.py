"""
chess_app.py
============
A proper QMainWindow that hosts GameExplorerWidget for game analysis.
Replaces the old ChessboardDialog (QDialog) approach with the window-controller
pattern found in qchess.
"""

import os

from PyQt5.QtCore import Qt, QSettings, QSize
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import (
    QMainWindow,
    QAction,
    QToolBar,
    QApplication,
    QMessageBox,
)
import qtawesome as qta

from widgets.game_explorer_widget import GameExplorerWidget


class ChessAppWindow(QMainWindow):
    """Stand-alone main window that displays a chess game for analysis.

    It wraps ``GameExplorerWidget`` (which already contains the board,
    engine, PGN browser, navigation controls, etc.) and exposes a thin
    public API so ``AppController`` can drive it without knowing its
    internals.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chess App — Game Explorer")
        self.resize(1200, 780)
        self.is_dark = True

        # Central widget — the full-featured game explorer
        self.explorer = GameExplorerWidget(self, html_style=self.is_dark)
        self.setCentralWidget(self.explorer)

        # Toolbar
        self._init_toolbar()

        # Restore geometry if previously saved
        geo = QSettings("CQLiApp", "ChessWindowLayout").value("geometry")
        if geo:
            self.restoreGeometry(geo)

    # ──────────────────────── Public API ────────────────────────

    def load_game(self, game_data: dict):
        """Load a game from a metadata dict that contains a 'PGN' key.

        Called by ``AppController._on_game_selected``.
        """
        white = game_data.get("White", "?")
        black = game_data.get("Black", "?")
        event = game_data.get("Event", "")
        title_parts = [f"{white} vs {black}"]
        if event:
            title_parts.append(event)
        self.setWindowTitle("Chess App — " + " | ".join(title_parts))

        # Delegate to the explorer widget
        self.explorer.load_game(game_data)

    def set_theme(self, is_dark: bool):
        """Switch between dark and light themes."""
        self.is_dark = is_dark
        self.explorer.set_theme(is_dark)

    # ──────────────────────── Toolbar ────────────────────────

    def _init_toolbar(self):
        tb = QToolBar("Main Toolbar", self)
        tb.setObjectName("chess_app_toolbar")
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(tb)

        flip_act = QAction(
            qta.icon("ei.refresh", color="#a9aea7"), "Flip Board", self
        )
        flip_act.setShortcut("Ctrl+F")
        flip_act.triggered.connect(self.explorer.flip_board)
        tb.addAction(flip_act)

        save_act = QAction(
            qta.icon("fa5s.save", color="#a9aea7"), "Save PGN", self
        )
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.explorer.save_pgn)
        tb.addAction(save_act)

        copy_act = QAction(
            qta.icon("fa5s.copy", color="#a9aea7"), "Copy PGN", self
        )
        copy_act.setShortcut("Ctrl+C")
        copy_act.triggered.connect(self.explorer.copy_pgn)
        tb.addAction(copy_act)

        tb.addSeparator()

        start_act = QAction(
            qta.icon("ph.caret-double-left-fill", color="#a9aea7"), "Jump to Start", self
        )
        start_act.triggered.connect(self.explorer.jump_to_start)
        tb.addAction(start_act)

        back_act = QAction(
            qta.icon("mdi.skip-previous", color="#a9aea7"), "Previous Move", self
        )
        back_act.triggered.connect(self.explorer.backward)
        tb.addAction(back_act)

        fwd_act = QAction(
            qta.icon("mdi.skip-next", color="#a9aea7"), "Next Move", self
        )
        fwd_act.triggered.connect(self.explorer.forward)
        tb.addAction(fwd_act)

        end_act = QAction(
            qta.icon("ph.caret-double-right-fill", color="#a9aea7"), "Jump to End", self
        )
        end_act.triggered.connect(self.explorer.jump_to_end)
        tb.addAction(end_act)

    # ──────────────────────── Window Events ────────────────────────

    def closeEvent(self, event):
        """Save geometry and hide the window on close.

        The window is hidden rather than destroyed so the controller can
        reuse it for the next game (matching the qchess lazy-creation approach).
        The engine is stopped here; it will be restarted when the window is
        shown again and analysis is toggled on.
        """
        QSettings("CQLiApp", "ChessWindowLayout").setValue(
            "geometry", self.saveGeometry()
        )
        # Stop the engine without destroying the widget
        try:
            self.explorer.engine.quit()
        except Exception:
            pass

        # Hide instead of closing so we can reuse this window
        event.ignore()
        self.hide()
