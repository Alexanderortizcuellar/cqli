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
from PyQt5.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QFont
import qtawesome as qta
import re
import chess

from core.move_manager import MoveManager
from core.engine import ChessEngine
from widgets.chessboard_widget import ChessBoardWidget
from widgets.game_metadata_widget import GameMetadataWidget
from widgets.move_list_widget import MovesListWidget
from widgets.analysis_widget import AnalysisWidget


class VariationsDialog(QDialog):
    def __init__(self, variations: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Variation")
        self.resize(300, 200)

        layout = QVBoxLayout(self)
        self.selected_index = None

        for index, item in variations.items():
            button = QPushButton(f"{item['san']}")
            button.setFont(QFont("Segoe UI", 12))
            button.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; }")
            button.clicked.connect(lambda _, idx=index: self.select_variation(idx))
            layout.addWidget(button)

    def select_variation(self, index):
        self.selected_index = index
        self.accept()


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

        self.header_widget = None

        self.browser = MovesListWidget(self, self.move_manager)
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

        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())

    def load_game(self, game_info: dict):
        """Loads a PGN game into the browser."""
        self.analysis_widget.check_analysis.setChecked(False)
        self.toggle_analysis(False)

        pgn_text = game_info.get("PGN", "")
        self.move_manager.update_pgn(pgn_text)
        self.move_manager.jump_to_start()

        if self.header_widget:
            self.right_layout.removeWidget(self.header_widget)
            self.header_widget.deleteLater()

        self.header_widget = GameMetadataWidget(game_info)
        self.right_layout.insertWidget(1, self.header_widget)

        start_fen = self.move_manager.current_node.board().fen()
        self.chessboard.update_board(start_fen)
        self.display_pgn()

    def display_pgn(self):
        """Syncs move manager html moves list into QTextBrowser."""
        self.browser.setHtml(self.move_manager.html)

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
            self.engine.quit()
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

    def send_position(self):
        """Send the current FEN position to Stockfish for evaluation."""
        if self.engine.is_running():
            self.engine.send_command("stop")
            self.analysis_widget.reset_lines()
            fen = self.chessboard.fen()
            self.engine.send_position(fen, mode="infinite")

    def on_analysis_updated(self, info: dict):
        """Slot triggered when engine finishes a depth PV line."""
        self.analysis_widget.update_analysis(info, self.chessboard.fen())

        if info.get("multipv", 1) == 1:
            score_type = info.get("score_type")
            score_value = info.get("score_value", 0)

            if self.chessboard.turn == chess.BLACK:
                score_value = -score_value

            self.chessboard.eval_bar.setEngineScore(
                {"type": score_type, "value": score_value}
            )

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

        self.display_pgn()

    def closeEvent(self, event):
        """Quit the engine process when the window closes."""
        self.engine.quit()
        event.accept()
