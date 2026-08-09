from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QDialog,
    QApplication,
    QSplitter,
)
from PyQt5.QtCore import QSize, Qt, QUrl, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QFont
import qtawesome as qta
import re
import chess

from core.move_manager import MoveManager
from core.engine import ChessEngine
from widgets.chessboard_widget import ChessBoardWidget
from widgets.painter_pgn_browser import QPainterPGNBrowser
from widgets.analysis_widget import AnalysisWidget
from dialogs.variations_dlg import VariationsDialog

class GameExplorerWidget(QWidget):
    """
    Main board panel combining the graphical board, engine analysis, metadata,
    moves navigation list, and action buttons.
    """

    gameSaved = pyqtSignal(str)  # Emits the updated PGN string

    def __init__(self, parent=None, html_style=False):
        super().__init__(parent)
        self.html_style = html_style

        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Engine")
        engine_path = settings.value("path", "stockfish")
        if not engine_path:
            engine_path = "stockfish"
        self.move_manager = MoveManager()
        self.move_manager.change_html_style(self.html_style)
        self.engine = ChessEngine(engine_path, self)

        # ── Anti-lag: analysis throttle timer ──────────────────────────────
        # Batches rapid engine info signals into at most one UI update per 100 ms.
        self._analysis_update_timer = QTimer(self)
        self._analysis_update_timer.setSingleShot(True)
        self._analysis_update_timer.setInterval(100)
        self._analysis_update_timer.timeout.connect(self._process_pending_analysis)
        self._pending_analysis: dict = {}      # multipv → latest info dict
        self._pending_fen: str | None = None
        self._has_first_update: bool = False   # suppress timer for very first depth

        # ── Anti-lag: engine debounce timer ───────────────────────────────
        # Delays sending a new position to the engine by 150 ms during navigation
        # so that scrolling through moves quickly only triggers one search start.
        self._engine_debounce = QTimer(self)
        self._engine_debounce.setSingleShot(True)
        self._engine_debounce.setInterval(150)
        self._engine_debounce.timeout.connect(self._run_debounced_send_position)
        self._last_move_time: float = 0.0

        # Enable keyboard focus for navigation
        self.setFocusPolicy(Qt.StrongFocus)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left Side: Chessboard Wrapper
        self.left_widget = QWidget()
        left_layout = QVBoxLayout(self.left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        self.chessboard = ChessBoardWidget(self, size=520)
        left_layout.addWidget(self.chessboard, 1)
        splitter.addWidget(self.left_widget)

        # Right Side: Analysis Panel + PGN Browser + Controls
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(5, 5, 5, 5)
        self.right_layout.setSpacing(6)

        self.analysis_widget = AnalysisWidget(self)
        self.analysis_widget.set_theme(self.html_style)
        self.right_layout.addWidget(self.analysis_widget)

        self.browser = QPainterPGNBrowser(self, self.move_manager)
        self.right_layout.addWidget(self.browser, 1)

        # Navigation Bar
        self.navigation_layout = QHBoxLayout()
        self.navigation_layout.setSpacing(4)

        self.jump_to_start_btn = QPushButton()
        self.jump_to_start_btn.setObjectName("nav-btn")
        self.jump_to_start_btn.setCursor(Qt.PointingHandCursor)
        self.jump_to_start_btn.setIcon(
            qta.icon(
                "ph.caret-double-left-fill",
                color="#E5E7EB" if self.html_style else "#312e2b",
            )
        )
        self.jump_to_start_btn.setIconSize(QSize(24, 24))

        self.backward_btn = QPushButton()
        self.backward_btn.setObjectName("nav-btn")
        self.backward_btn.setCursor(Qt.PointingHandCursor)
        self.backward_btn.setIcon(
            qta.icon(
                "mdi.skip-previous", color="#E5E7EB" if self.html_style else "#312e2b"
            )
        )
        self.backward_btn.setIconSize(QSize(24, 24))
        self.backward_btn.setShortcut("Left")

        self.forward_btn = QPushButton()
        self.forward_btn.setObjectName("nav-btn")
        self.forward_btn.setCursor(Qt.PointingHandCursor)
        self.forward_btn.setIcon(
            qta.icon("mdi.skip-next", color="#E5E7EB" if self.html_style else "#312e2b")
        )
        self.forward_btn.setIconSize(QSize(24, 24))
        self.forward_btn.setShortcut("Right")

        self.jump_to_end_btn = QPushButton()
        self.jump_to_end_btn.setObjectName("nav-btn")
        self.jump_to_end_btn.setCursor(Qt.PointingHandCursor)
        self.jump_to_end_btn.setIcon(
            qta.icon(
                "ph.caret-double-right-fill",
                color="#E5E7EB" if self.html_style else "#312e2b",
            )
        )
        self.jump_to_end_btn.setIconSize(QSize(24, 24))

        self.flip_btn = QPushButton()
        self.flip_btn.setObjectName("nav-btn")
        self.flip_btn.setCursor(Qt.PointingHandCursor)
        self.flip_btn.setIcon(
            qta.icon("ei.refresh", color="#E5E7EB" if self.html_style else "#312e2b")
        )
        self.flip_btn.setIconSize(QSize(24, 24))

        self.navigation_layout.addWidget(self.jump_to_start_btn)
        self.navigation_layout.addWidget(self.backward_btn)
        self.navigation_layout.addWidget(self.forward_btn)
        self.navigation_layout.addWidget(self.jump_to_end_btn)
        self.navigation_layout.addWidget(self.flip_btn)
        self.right_layout.addLayout(self.navigation_layout)

        # Action Bar (Save/Copy)
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(10)

        self.save_btn = QPushButton("Save PGN Changes")
        self.save_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self.save_btn.setCursor(Qt.PointingHandCursor)

        self.copy_btn = QPushButton("Copy PGN")
        self.copy_btn.setIcon(qta.icon("fa5s.copy", color="white"))
        self.copy_btn.setCursor(Qt.PointingHandCursor)

        self.actions_layout.addWidget(self.save_btn)
        self.actions_layout.addWidget(self.copy_btn)
        self.right_layout.addLayout(self.actions_layout)

        splitter.addWidget(self.right_widget)
        splitter.setSizes([550, 450])

        # --- Signal Connections ---
        self.jump_to_start_btn.clicked.connect(self.jump_to_start)
        self.backward_btn.clicked.connect(self.backward)
        self.forward_btn.clicked.connect(self.forward)
        self.jump_to_end_btn.clicked.connect(self.jump_to_end)
        self.flip_btn.clicked.connect(self.flip_board)
        self.save_btn.clicked.connect(self.save_pgn)
        self.copy_btn.clicked.connect(self.copy_pgn)

        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.moveMade.connect(self.handle_move)
        self.chessboard.fenChanged.connect(self.send_position)

        self.analysis_widget.evaluationToggled.connect(self.toggle_analysis)
        self.analysis_widget.configClicked.connect(self.show_engine_config_dialog)
        self.engine.analysisUpdated.connect(self.on_analysis_updated)
        self.engine.depthChanged.connect(
            lambda depth: self.analysis_widget.set_depth(f"depth {depth}")
        )

        # pgnChanged triggers a layout rebuild; activeNodeChanged scrolls to the active move
        self.move_manager.pgnChanged.connect(lambda _: self.browser.rebuild_layout(force=True))
        self.move_manager.activeNodeChanged.connect(self.browser.update_active_index)

        # Event filter for mouse wheel navigation on chessboard
        self.chessboard.installEventFilter(self)
        self.chessboard.board_view.installEventFilter(self)
        self.chessboard.board_view.viewport().installEventFilter(self)

    def load_game(self, game_info: dict):
        """Loads a PGN game into the browser."""
        self.analysis_widget.check_analysis.setChecked(False)
        self.toggle_analysis(False)

        pgn_text = game_info.get("PGN", "")
        self.move_manager.update_pgn(pgn_text)
        self.move_manager.jump_to_start()

        start_fen = self.move_manager.current_node.board().fen()
        self.chessboard.update_board(start_fen)
        self.browser.rebuild_layout(force=True)

    def display_pgn(self):
        """Triggers a full rebuild of the painter PGN browser."""
        self.browser.rebuild_layout(force=True)

    def handle_move(self, move_uci: str):
        """Handle move executed on the graphical chessboard."""
        self.move_manager.make_move(move_uci)
        self.display_pgn()

    def forward(self):
        """Redo or go forward in the variation tree."""
        if self.move_manager.has_variations():
            variations = self.move_manager.get_current_node_variations()
            if len(variations) > 1:
                dialog = VariationsDialog(variations, self)
                if dialog.exec_() != QDialog.Accepted:
                    return
                if dialog.selected_index is None:
                    return
                self.move_manager.redo(dialog.selected_index)
            else:
                self.move_manager.redo()

            node = self.move_manager.current_node
            self.chessboard.update_board(node.board().fen(), last_move=node.move)
            self.display_pgn()

    def backward(self):
        """Undo or go backward in the variation tree."""
        self.move_manager.undo()
        node = self.move_manager.current_node
        self.chessboard.update_board(node.board().fen(), last_move=node.move)
        self.display_pgn()

    def jump_to_start(self):
        """Jump back to the initial starting position of the game."""
        self.move_manager.jump_to_start()
        self.chessboard.update_board(
            self.move_manager.current_node.board().fen(), last_move=None
        )
        self.display_pgn()

    def jump_to_end(self):
        """Jump straight to the final move of the mainline."""
        self.move_manager.jump_to_end()
        node = self.move_manager.current_node
        self.chessboard.update_board(node.board().fen(), last_move=node.move)
        self.display_pgn()

    def flip_board(self):
        """Flips the chessboard orientation."""
        self.chessboard.flip()
        self.chessboard.eval_bar.setFlipped(not self.chessboard.eval_bar._flipped)

    def on_anchor_clicked(self, url: QUrl):
        """Jump to a specific move index when its link is clicked in MovesListWidget."""
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            idx = int(match.group(1))
            self.move_manager.jump_to(idx)
            node = self.move_manager.current_node
            self.chessboard.update_board(node.board().fen(), last_move=node.move)
            self.display_pgn()

    def toggle_analysis(self, checked: bool):
        """Start or stop the background Stockfish analysis."""
        if checked:
            if not self.engine.is_running():
                from PyQt5.QtCore import QSettings

                settings = QSettings("TestChessApp", "Engine")

                path = settings.value("path", "stockfish")
                if not path:
                    path = "stockfish"

                try:
                    threads = int(settings.value("threads", 4))
                except Exception:
                    threads = 4

                try:
                    hash_val = int(settings.value("hash", 1024))
                except Exception:
                    hash_val = 1024

                try:
                    multipv = int(settings.value("multipv", 1))
                except Exception:
                    multipv = 1

                try:
                    skill = int(settings.value("skill", 20))
                except Exception:
                    skill = 20

                ponder = settings.value("ponder", False, bool)
                syzygy = settings.value("syzygy", "")

                self.engine.set_settings(
                    {
                        "path": path,
                        "threads": threads,
                        "hash": hash_val,
                        "multipv": multipv,
                        "skill": skill,
                        "ponder": ponder,
                        "syzygy": syzygy,
                    }
                )
            self.chessboard.set_eval_bar_visible(True)
            self.send_position()
        else:
            # stop_search (not quit) keeps the engine process alive — faster to
            # restart on next analysis toggle, and the engine debounce timer
            # won't fire against a dead process.
            self._engine_debounce.stop()
            self._clear_pending_analysis()
            self.engine.stop_search()
            self.chessboard.set_eval_bar_visible(False)
            self.analysis_widget.clear()

    def show_engine_config_dialog(self):
        """Show engine configuration dialog and restart engine if running."""
        from dialogs.engine_dlg import EngineConfigDialog

        dlg = EngineConfigDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            if self.engine.is_running():
                self.engine.quit()
                self.toggle_analysis(True)

    def send_position(self, force: bool = False):
        """Send current FEN to engine — with fast-navigation debouncing.

        If the user is navigating faster than 4 moves/s the engine search is
        stopped immediately and a 150 ms debounce timer is started so the
        engine only resumes once the user pauses.  This eliminates the stutter
        caused by repeatedly stopping/starting Stockfish on every arrow key.
        """
        import time

        board = self.move_manager.current_node.board()
        if board.is_game_over():
            if self.engine.is_running():
                self.engine.stop_search()
                self.analysis_widget.reset_lines()
            if board.is_checkmate():
                winner = "white" if board.turn == chess.BLACK else "black"
                self.chessboard.eval_bar.setEngineScore({"type": "checkmate", "winner": winner})
            else:
                self.chessboard.eval_bar.setEngineScore({"type": "draw"})
            return

        # Do not start engine evaluation if analysis is disabled in the UI
        if not self.analysis_widget.check_analysis.isChecked():
            return

        if not self.engine.is_running():
            return

        now = time.monotonic()
        dt = now - self._last_move_time
        self._last_move_time = now
        is_fast = dt < 0.25  # faster than 4 moves/s

        self._has_first_update = False
        self._clear_pending_analysis()

        if is_fast:
            # Stop current search immediately; let debounce timer restart it
            self.engine.stop_search()
            self._engine_debounce.start()
        else:
            self._engine_debounce.stop()
            self._run_debounced_send_position()

    def _run_debounced_send_position(self):
        """Actually send the position to the engine (called after debounce)."""
        if not self.engine.is_running() or not self.analysis_widget.check_analysis.isChecked():
            return
        self.analysis_widget.reset_lines()
        fen = self.chessboard.fen()
        self.engine.send_position(fen, mode="infinite")

    def _clear_pending_analysis(self):
        """Discard any buffered analysis info that hasn't been rendered yet."""
        self._pending_analysis.clear()
        self._pending_fen = None
        self._analysis_update_timer.stop()

    def keyPressEvent(self, event):
        """Handle arrow keys globally inside this widget hierarchy for navigation."""
        if event.key() == Qt.Key_Right:
            self.forward()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.backward()
            event.accept()
        else:
            super().keyPressEvent(event)

    def on_analysis_updated(self, info: dict):
        """Buffer incoming engine info and render at most once per 100 ms.

        The engine can emit dozens of `info depth …` lines per second — each
        triggering HTML re-rendering.  Batching them eliminates the jank.
        """
        if self.move_manager.current_node.board().is_game_over():
            return

        # Update eval bar immediately (cheap — no HTML)
        if info.get("multipv", 1) == 1:
            score_type = info.get("score_type")
            score_value = info.get("score_value", 0)
            if self.chessboard.turn == chess.BLACK:
                score_value = -score_value
            self.chessboard.eval_bar.setEngineScore({"type": score_type, "value": score_value})

        # Buffer for batched HTML update
        multipv = info.get("multipv", 1)
        self._pending_analysis[multipv] = info
        self._pending_fen = self.chessboard.fen()

        if not self._has_first_update:
            # Render the very first depth result immediately for responsiveness
            self._has_first_update = True
            self._process_pending_analysis()
        elif not self._analysis_update_timer.isActive():
            self._analysis_update_timer.start()

    def _process_pending_analysis(self):
        """Flush buffered analysis lines to AnalysisWidget in one render call."""
        if not self._pending_analysis:
            return
        infos = sorted(self._pending_analysis.values(), key=lambda x: x.get("multipv", 1))
        fen = self._pending_fen
        self._pending_analysis.clear()
        self.analysis_widget.update_analysis_batch(infos, fen)

    def save_pgn(self):
        """Triggered when the user wants to save edits back."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PGN File", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.move_manager.get_pgn())
                self.gameSaved.emit(self.move_manager.get_pgn())
            except Exception as e:
                print(f"Error saving PGN: {e}")

    def copy_pgn(self):
        """Copies the PGN data to system clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.move_manager.get_pgn())

    def set_theme(self, is_dark: bool):
        """Update style sheets based on theme changes."""
        self.html_style = is_dark
        self.move_manager.change_html_style(is_dark)
        self.analysis_widget.set_theme(is_dark)

        icon_color = "#E5E7EB" if is_dark else "#312e2b"
        self.jump_to_start_btn.setIcon(
            qta.icon("ph.caret-double-left-fill", color=icon_color)
        )
        self.backward_btn.setIcon(qta.icon("mdi.skip-previous", color=icon_color))
        self.forward_btn.setIcon(qta.icon("mdi.skip-next", color=icon_color))
        self.jump_to_end_btn.setIcon(
            qta.icon("ph.caret-double-right-fill", color=icon_color)
        )
        self.flip_btn.setIcon(qta.icon("ei.refresh", color=icon_color))

        self.browser.rebuild_layout(force=True)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel:
            if watched in (
                self.chessboard,
                self.chessboard.board_view,
                self.chessboard.board_view.viewport(),
            ):
                delta = event.angleDelta().y()
                if delta > 0:
                    self.forward()
                elif delta < 0:
                    self.backward()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        """Quit the engine process when the window closes."""
        self.engine.quit()
        event.accept()
