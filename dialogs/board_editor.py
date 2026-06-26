import sys
import chess
import chess.svg
import qtawesome as qta
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGridLayout,
    QButtonGroup,
    QDialog,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QDialogButtonBox,
    QFrame,
)
from PyQt5.QtCore import Qt, QSize, QByteArray, QMimeData
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QDrag
from PyQt5.QtSvg import QSvgRenderer


def get_piece_pixmap(piece, size=60):
    """Generates a QPixmap from the python-chess SVG piece."""
    svg_string = chess.svg.piece(piece)
    renderer = QSvgRenderer(QByteArray(svg_string.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


class SquareWidget(QLabel):
    """A custom label representing a single square on the chessboard."""

    def __init__(self, square_index, is_light, editor_parent):
        super().__init__()
        self.square_index = square_index
        self.editor_parent = editor_parent
        self.base_color = "#F0D9B5" if is_light else "#B58863"
        self.setFixedSize(60, 60)
        self.setAlignment(Qt.AlignCenter)

        self.setAcceptDrops(True)
        self.drag_start_pos = None

        self.update_background()

    def update_background(self, selected=False):
        """Updates the background color, highlighting if selected."""
        color = "#99CC99" if selected else self.base_color
        self.setStyleSheet(f"background-color: {color}; border: none;")

    def mousePressEvent(self, event):
        """Registers the start of a potential drag and handles normal clicks."""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.editor_parent.square_clicked(self.square_index)

    def mouseMoveEvent(self, event):
        """Initiates the drag action if the mouse moves far enough."""
        if not self.drag_start_pos:
            return

        if not (event.buttons() & Qt.LeftButton):
            return

        if (
            event.pos() - self.drag_start_pos
        ).manhattanLength() < QApplication.startDragDistance():
            return

        active_button = self.editor_parent.tool_group.checkedButton()
        if (
            not active_button
            or self.editor_parent.tools_map.get(active_button) != "hand"
        ):
            return

        if not self.editor_parent.board.piece_at(self.square_index):
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.square_index))
        drag.setMimeData(mime_data)

        if self.pixmap():
            drag.setPixmap(self.pixmap())
            drag.setHotSpot(self.pixmap().rect().center())

        self.clear()
        drag.exec_(Qt.MoveAction)
        self.editor_parent.update_board_ui()

    def dragEnterEvent(self, event):
        """Accepts the drag if it contains our text data."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Reads the origin square from the drag data and executes the move."""
        origin_index = int(event.mimeData().text())
        self.editor_parent.handle_drop(origin_index, self.square_index)
        event.acceptProposedAction()


class ChessBoardEditorGrid(QWidget):
    """
    Renders strictly the 8x8 chessboard grid.
    Decoupled from control panels for modularity and layout flexibility.
    """

    def __init__(self, parent_dialog=None):
        super().__init__()
        self.parent_dialog = parent_dialog
        self.board = chess.Board()
        self.selected_square = None

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tools_map = {}
        self.square_widgets = {}
        self.on_board_changed_cb = None
        self.block_cb = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Chessboard container frame with a clean border
        self.board_frame = QFrame()
        self.board_frame.setObjectName("board_frame")
        self.board_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.board_frame.setStyleSheet(
            "QFrame#board_frame { border: 3px solid #3E3E3E; border-radius: 4px; }"
        )

        self.board_layout = QGridLayout(self.board_frame)
        self.board_layout.setSpacing(0)
        self.board_layout.setContentsMargins(0, 0, 0, 0)

        self.flipped = False
        for rank in range(7, -1, -1):
            for file in range(8):
                square_index = chess.square(file, rank)
                is_light = (file + rank) % 2 != 0

                square_widget = SquareWidget(square_index, is_light, self)
                self.square_widgets[square_index] = square_widget
                self.board_layout.addWidget(square_widget, 7 - rank, file)

        layout.addWidget(self.board_frame)
        self.update_board_ui()

    def toggle_flip(self):
        self.flipped = not getattr(self, "flipped", False)
        for rank in range(8):
            for file in range(8):
                square_index = chess.square(file, rank)
                widget = self.square_widgets[square_index]
                self.board_layout.removeWidget(widget)
                if self.flipped:
                    self.board_layout.addWidget(widget, rank, 7 - file)
                else:
                    self.board_layout.addWidget(widget, 7 - rank, file)

    def square_clicked(self, square_index):
        active_button = self.tool_group.checkedButton()
        if not active_button:
            return

        current_tool = self.tools_map.get(active_button)

        if current_tool == "trash":
            self.board.remove_piece_at(square_index)
            self.selected_square = None
        elif isinstance(current_tool, chess.Piece):
            self.board.set_piece_at(square_index, current_tool)
            self.selected_square = None
        elif current_tool == "hand":
            if self.selected_square is None:
                if self.board.piece_at(square_index):
                    self.selected_square = square_index
            else:
                if self.selected_square != square_index:
                    moving_piece = self.board.piece_at(self.selected_square)
                    if moving_piece:
                        self.board.set_piece_at(square_index, moving_piece)
                        self.board.remove_piece_at(self.selected_square)
                self.selected_square = None

        self.update_board_ui()

    def handle_drop(self, origin_index, target_index):
        if origin_index != target_index:
            moving_piece = self.board.piece_at(origin_index)
            if moving_piece:
                self.board.set_piece_at(target_index, moving_piece)
                self.board.remove_piece_at(origin_index)

        self.selected_square = None
        self.update_board_ui()

    def update_board_ui(self):
        for square_index, widget in self.square_widgets.items():
            piece = self.board.piece_at(square_index)
            if piece:
                widget.setPixmap(get_piece_pixmap(piece))
            else:
                widget.clear()

            is_selected = square_index == self.selected_square
            widget.update_background(selected=is_selected)

        # Trigger FEN sync callback to keepTurn/Castling properties up to date
        if self.on_board_changed_cb and not self.block_cb:
            self.on_board_changed_cb()


class BoardEditorDlg(QDialog):
    """
    Position and FEN editor dialog presenting the Board on the left and FEN settings on the right.
    """

    def __init__(self, parent=None, initial_fen=None):
        super().__init__(parent)
        self.setWindowTitle("Position Editor")
        self.setMinimumSize(850, 520)

        # Premium selection style for the piece palette
        self.setStyleSheet(
            """
            QPushButton#palette_btn {
                border: 1px solid #CCC;
                border-radius: 4px;
                background-color: #F9F9F9;
            }
            QPushButton#palette_btn:hover {
                background-color: #F0F0F0;
            }
            QPushButton#palette_btn:checked {
                border: 2.5px solid #2563EB;
                background-color: #EFF6FF;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """
        )

        # Main horizontal layout (Board on Left, Controls on Right)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        # 1. Left Side - Chessboard Grid
        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignCenter)
        self.board_editor = ChessBoardEditorGrid(self)
        left_layout.addWidget(self.board_editor)
        main_layout.addLayout(left_layout)

        # 2. Right Side - Palette & Control Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # --- Palette Group ---
        palette_group = QGroupBox("Piece Palette")
        palette_layout = QVBoxLayout(palette_group)
        palette_layout.setSpacing(8)

        # Hand / Pointer and Trash / Eraser tools
        tools_layout = QHBoxLayout()
        self.btn_hand = QPushButton(" Hand / Move")
        self.btn_hand.setIcon(qta.icon("fa5s.hand-pointer"))
        self.btn_hand.setCheckable(True)
        self.btn_hand.setFixedHeight(36)
        self.btn_hand.setCursor(Qt.PointingHandCursor)
        self.board_editor.tool_group.addButton(self.btn_hand)
        self.board_editor.tools_map[self.btn_hand] = "hand"

        self.btn_trash = QPushButton(" Eraser")
        self.btn_trash.setIcon(qta.icon("fa5s.eraser"))
        self.btn_trash.setCheckable(True)
        self.btn_trash.setFixedHeight(36)
        self.btn_trash.setCursor(Qt.PointingHandCursor)
        self.board_editor.tool_group.addButton(self.btn_trash)
        self.board_editor.tools_map[self.btn_trash] = "trash"

        tools_layout.addWidget(self.btn_hand)
        tools_layout.addWidget(self.btn_trash)
        palette_layout.addLayout(tools_layout)

        # White pieces row
        white_layout = QHBoxLayout()
        white_layout.setSpacing(4)
        for pt in [
            chess.KING,
            chess.QUEEN,
            chess.ROOK,
            chess.BISHOP,
            chess.KNIGHT,
            chess.PAWN,
        ]:
            piece = chess.Piece(pt, chess.WHITE)
            btn = QPushButton()
            btn.setObjectName("palette_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(QIcon(get_piece_pixmap(piece, size=40)))
            btn.setIconSize(QSize(40, 40))
            btn.setCheckable(True)
            btn.setFixedSize(48, 48)
            self.board_editor.tool_group.addButton(btn)
            self.board_editor.tools_map[btn] = piece
            white_layout.addWidget(btn)
        palette_layout.addLayout(white_layout)

        # Black pieces row
        black_layout = QHBoxLayout()
        black_layout.setSpacing(4)
        for pt in [
            chess.KING,
            chess.QUEEN,
            chess.ROOK,
            chess.BISHOP,
            chess.KNIGHT,
            chess.PAWN,
        ]:
            piece = chess.Piece(pt, chess.BLACK)
            btn = QPushButton()
            btn.setObjectName("palette_btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(QIcon(get_piece_pixmap(piece, size=40)))
            btn.setIconSize(QSize(40, 40))
            btn.setCheckable(True)
            btn.setFixedSize(48, 48)
            self.board_editor.tool_group.addButton(btn)
            self.board_editor.tools_map[btn] = piece
            black_layout.addWidget(btn)
        palette_layout.addLayout(black_layout)

        right_layout.addWidget(palette_group)

        # --- FEN Properties Group ---
        properties_group = QGroupBox("FEN properties")
        properties_layout = QVBoxLayout(properties_group)
        properties_layout.setSpacing(10)

        # Turn selector
        turn_layout = QHBoxLayout()
        turn_layout.addWidget(QLabel("Active Side:"))
        self.turn_combo = QComboBox()
        self.turn_combo.addItems(["White to move", "Black to move"])
        self.turn_combo.currentIndexChanged.connect(self.update_fen_from_controls)
        turn_layout.addWidget(self.turn_combo)
        turn_layout.addStretch()
        properties_layout.addLayout(turn_layout)

        # Castling checkboxes
        castling_layout = QHBoxLayout()
        self.castling_wk = QCheckBox("WK")
        self.castling_wq = QCheckBox("WQ")
        self.castling_bk = QCheckBox("BK")
        self.castling_bq = QCheckBox("BQ")

        for cb in [
            self.castling_wk,
            self.castling_wq,
            self.castling_bk,
            self.castling_bq,
        ]:
            cb.toggled.connect(self.update_fen_from_controls)
            castling_layout.addWidget(cb)
        castling_layout.addStretch()
        properties_layout.addWidget(QLabel("Castling Rights:"))
        properties_layout.addLayout(castling_layout)

        right_layout.addWidget(properties_group)

        # --- FEN Input / Output ---
        fen_label = QLabel("Generated FEN String:")
        fen_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(fen_label)

        fen_display_layout = QHBoxLayout()
        self.fen_display = QLineEdit()
        self.fen_display.setReadOnly(True)
        self.fen_display.setStyleSheet(
            "QLineEdit { font-family: Consolas; font-size: 11px; padding: 6px; background-color: #F3F4F6; }"
        )

        self.btn_copy_fen = QPushButton()
        self.btn_copy_fen.setIcon(qta.icon("fa5s.copy"))
        self.btn_copy_fen.setToolTip("Copy FEN to clipboard")
        self.btn_copy_fen.setCursor(Qt.PointingHandCursor)
        self.btn_copy_fen.setFixedSize(30, 30)
        self.btn_copy_fen.clicked.connect(self.copy_fen_to_clipboard)

        fen_display_layout.addWidget(self.fen_display)
        fen_display_layout.addWidget(self.btn_copy_fen)
        right_layout.addLayout(fen_display_layout)

        # --- Utility Actions ---
        utils_layout = QHBoxLayout()
        self.clear_btn = QPushButton(" Clear Board")
        self.clear_btn.setIcon(qta.icon("fa5s.times-circle"))
        self.clear_btn.clicked.connect(self.clear_board)
        self.clear_btn.setCursor(Qt.PointingHandCursor)

        self.reset_btn = QPushButton(" Reset Starting")
        self.reset_btn.setIcon(qta.icon("fa5s.history"))
        self.reset_btn.clicked.connect(self.reset_board)
        self.reset_btn.setCursor(Qt.PointingHandCursor)

        self.flip_btn = QPushButton(" Flip Board")
        self.flip_btn.setIcon(qta.icon("fa5s.retweet"))
        self.flip_btn.clicked.connect(self.flip_board)
        self.flip_btn.setCursor(Qt.PointingHandCursor)

        utils_layout.addWidget(self.clear_btn)
        utils_layout.addWidget(self.reset_btn)
        utils_layout.addWidget(self.flip_btn)
        utils_layout.addStretch()
        right_layout.addLayout(utils_layout)

        # --- Standard OK/Cancel ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        right_layout.addWidget(self.button_box)

        main_layout.addWidget(right_panel)

        # Synchronize board changes back to turning/castling checkboxes
        self.board_editor.on_board_changed_cb = self.sync_controls_to_board

        # Set default active tool (Hand / Move)
        self.btn_hand.setChecked(True)

        # Initialize FEN state
        if initial_fen:
            try:
                self.board_editor.board.set_fen(initial_fen)
                self.board_editor.update_board_ui()
            except ValueError:
                pass
        else:
            self.reset_board()

        self.sync_controls_to_board()

    def sync_controls_to_board(self):
        """Extracts turn/castling properties from the chess.Board state and checks UI controls."""
        board = self.board_editor.board
        self.turn_combo.setCurrentIndex(0 if board.turn == chess.WHITE else 1)
        self.castling_wk.setChecked(bool(board.castling_rights & chess.BB_H1))
        self.castling_wq.setChecked(bool(board.castling_rights & chess.BB_A1))
        self.castling_bk.setChecked(bool(board.castling_rights & chess.BB_H8))
        self.castling_bq.setChecked(bool(board.castling_rights & chess.BB_A8))
        self.fen_display.setText(board.fen())

    def update_fen_from_controls(self):
        """Translates turn/castling GUI selections back onto the chess.Board structure."""
        board = self.board_editor.board
        board.turn = chess.WHITE if self.turn_combo.currentIndex() == 0 else chess.BLACK

        # Block callbacks temporarily to prevent recursion
        self.board_editor.block_cb = True
        wk = chess.BB_H1 if self.castling_wk.isChecked() else 0
        wq = chess.BB_A1 if self.castling_wq.isChecked() else 0
        bk = chess.BB_H8 if self.castling_bk.isChecked() else 0
        bq = chess.BB_A8 if self.castling_bq.isChecked() else 0
        board.castling_rights = wk | wq | bk | bq
        self.board_editor.update_board_ui()
        self.board_editor.block_cb = False

        self.fen_display.setText(board.fen())

    def copy_fen_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.fen_display.text())

    def clear_board(self):
        self.board_editor.board.clear()
        self.board_editor.update_board_ui()
        self.sync_controls_to_board()

    def reset_board(self):
        self.board_editor.board.reset()
        self.board_editor.update_board_ui()
        self.sync_controls_to_board()

    def flip_board(self):
        self.board_editor.toggle_flip()

    def get_fen(self):
        return self.board_editor.board.fen()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = BoardEditorDlg()
    editor.show()
    sys.exit(app.exec_())
