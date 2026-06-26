from PyQt5.QtCore import Qt, QRegularExpression, QSize, QRect
from PyQt5.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QFont,
    QPainter,
    QTextCursor,
    QKeySequence,
)
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QCompleter,
    QTextEdit,
    QApplication,
    QPushButton,
    QDialog,
    QShortcut,
)
import qtawesome as qta
import sys
import re


# ===================================================
#                Syntax Highlighter
# ===================================================
class SqlHighlighter(QSyntaxHighlighter):
    """
    CQLi Syntax Highlighter supporting:
    - Keywords, functions, filters
    - Strings (single & double)
    - Numbers
    - Operators & punctuation
    - Single-line and multi-line comments
    Theme-aware colors.
    """

    def __init__(self, document, theme: str = "light"):
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self.commentStart = QRegularExpression(r"/\*")
        self.commentEnd = QRegularExpression(r"\*/")
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955"))  # green-ish

        self._keyword_regex = None
        self._function_regex = None

        self._init_formats(theme)
        self._compile_rules()

    # ---------- Theme handling ----------
    def _init_formats(self, theme: str):
        # VS Code-ish palette that works in both themes
        def color(hex_light, hex_dark):
            return QColor(hex_dark if theme == "dark" else hex_light)

        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(color("#0B5CAD", "#4FC1FF"))
        self.fmt_keyword.setFontWeight(QFont.Bold)

        self.fmt_function = QTextCharFormat()
        self.fmt_function.setForeground(color("#9C27B0", "#C792EA"))
        self.fmt_function.setFontWeight(QFont.DemiBold)

        self.fmt_string = QTextCharFormat()
        self.fmt_string.setForeground(color("#228B22", "#CE9178"))

        self.fmt_number = QTextCharFormat()
        self.fmt_number.setForeground(color("#B22222", "#D19A66"))

        self.fmt_comment = QTextCharFormat()
        self.fmt_comment.setForeground(color("#6B7280", "#6A9955"))  # gray/green

        self.fmt_operator = QTextCharFormat()
        self.fmt_operator.setForeground(color("#8B008B", "#C586C0"))

        self.fmt_piece_designator = QTextCharFormat()
        self.fmt_piece_designator.setForeground(color("#950BB1", "#2FDBD3"))
        self.fmt_piece_designator.setFontWeight(QFont.Bold)

    def setTheme(self, theme: str):
        """Call this when toggling theme; then rehighlight."""
        self._init_formats(theme)
        self.rules.clear()
        self._compile_rules()
        self.rehighlight()

    # ---------- Patterns ----------
    def _compile_rules(self):
        # Full list of CQL and CQLi keywords
        keywords = [
            "abs",
            "Aa",
            "and",
            "ascii",
            "assert",
            "atomic",
            "between",
            "black",
            "btm",
            "castle",
            "check",
            "child",
            "comment",
            "connectedpawns",
            "consecutivemoves",
            "countmoves",
            "currentmove",
            "currentposition",
            "currenttransform",
            "dark",
            "date",
            "depth",
            "dictionary",
            "distance",
            "doubledpawns",
            "down",
            "echo",
            "eco",
            "elo",
            "event",
            "eventdate",
            "false",
            "fen",
            "file",
            "find",
            "flip",
            "flipcolor",
            "fliphorizontal",
            "flipvertical",
            "from",
            "function",
            "gamenumber",
            "hascomment",
            "idealmate",
            "idealstalemate",
            "if",
            "in",
            "indexof",
            "initial",
            "initialposition",
            "int",
            "isbound",
            "isolatedpawns",
            "isunbound",
            "lastgamenumber",
            "lca",
            "legal",
            "left",
            "pseudolegal",
            "light",
            "local",
            "loop",
            "lowercase",
            "mainline",
            "makesquare",
            "mate",
            "message",
            "modelmate",
            "modelstalemate",
            "movenumber",
            "northeast",
            "northwest",
            "not",
            "notransform",
            "nullmove",
            "o-o",
            "o-o-o",
            "or",
            "originalcomment",
            "parent",
            "passedpawns",
            "path",
            "pathcount",
            "pathcountunfocused",
            "pathlastposition",
            "pathstatus",
            "persistent",
            "piece",
            "piecename",
            "pieceid",
            "pin",
            "player",
            "ply",
            "position",
            "positionid",
            "power",
            "primary",
            "pseudolegal",
            "puremate",
            "purestalemate",
            "rank",
            "ray",
            "readfile",
            "removecomment",
            "result",
            "reversecolor",
            "right",
            "rotate45",
            "rotate90",
            "secondary",
            "shift",
            "shifthorizontal",
            "shiftvertical",
            "sidetomove",
            "site",
            "sort",
            "sqrt",
            "square",
            "stalemate",
            "tag",
            "terminal",
            "to",
            "true",
            "try",
            "type",
            "typename",
            "unbind",
            "up",
            "uppercase",
            "variation",
            "virtualmainline",
            "while",
            "white",
            "wtm",
            "year",
            # --- New CQLi Specific Keywords ---
            "cqlbegin",
            "cqlend",
            "imagine",
            "reachableposition",
            "replace",
            "key",
            "speculative",
            "tourney_edition",
            "tourney_name",
            "tourney_year",
            "tourney_year_end",
            "tourney_year_part",
            "distinction",
        ]

        functions = [
            "cql",
            "writefile",
            "readfile",
            "settag",
            "str",
            "max",
            "min",
            "replace",
        ]
        piece_designators = [
            "A",
            "a",
            "B",
            "b",
            "K",
            "k",
            "N",
            "n",
            "P",
            "p",
            "Q",
            "q",
            "R",
            "r",
        ]
        files = ["c", "d", "e", "f", "g", "h"]
        squares = [
            f"{chr(file)}{column}" for file in range(97, 105) for column in range(1, 9)
        ]
        piece_designators.extend(squares)
        piece_designators.extend(files)

        # Keywords
        kw_pattern = r"\b(" + "|".join(keywords) + r")\b"
        self._keyword_regex = QRegularExpression(kw_pattern)
        self._keyword_regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self.rules.append((self._keyword_regex, self.fmt_keyword))

        # Functions (before functions' '(' )
        fn_pattern = r"\b(" + "|".join(functions) + r")(?=\s*\()"
        self._function_regex = QRegularExpression(fn_pattern)
        self._function_regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self.rules.append((self._function_regex, self.fmt_function))

        # Parameters (everything inside parentheses)
        param_pattern = r"\(([^)]*)\)"
        self._param_regex = QRegularExpression(param_pattern)
        self.rules.append((self._param_regex, self.fmt_string))

        # Numbers
        self.rules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), self.fmt_number))

        # inside brackets
        self.rules.append(
            (
                QRegularExpression(r"\[.*?\]"),
                self.fmt_keyword,
            )
        )
        # Piece designators
        pi_pattern = r"\b(" + "|".join(piece_designators) + r")\b"
        self._pi_regex = QRegularExpression(pi_pattern)
        self._pi_regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self.rules.append((self._pi_regex, self.fmt_piece_designator))

        # Operators & punctuation
        self.rules.append((QRegularExpression(r"[+\-*/=<>\|!&_]+"), self.fmt_operator))
        self.rules.append((QRegularExpression(r"[(),;]"), self.fmt_operator))
        self.rules.append((QRegularExpression(r"[.]"), self.fmt_keyword))

        # Strings: single & double quotes (evaluate after operators/keywords to override them)
        self.rules.append(
            (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), self.fmt_string)
        )
        self.rules.append(
            (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), self.fmt_string)
        )

        # Comments (evaluate last so they override everything else, e.g. operators/keywords inside comments)
        self.rules.append(
            (
                QRegularExpression(
                    r"/\*.*?\*/", QRegularExpression.DotMatchesEverythingOption
                ),
                self.fmt_comment,
            )
        )
        self.rules.append((QRegularExpression(r"//[^\n]*"), self.fmt_comment))

    # ---------- Highlight ----------
    def highlightBlock(self, text: str):
        # Apply single-line rules
        for regex, fmt in self.rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                start = m.capturedStart()
                length = m.capturedLength()
                if start >= 0 and length > 0:
                    self.setFormat(start, length, fmt)

        # Handle multi-line comments /* ... */
        self.setCurrentBlockState(0)

        start_idx = 0
        if self.previousBlockState() != 1:
            start_match = self.commentStart.match(text, 0)
            start_idx = start_match.capturedStart()
        else:
            start_idx = 0

        while start_idx >= 0:
            end_match = self.commentEnd.match(text, start_idx)
            end_idx = end_match.capturedStart()

            if end_idx == -1:
                # Comment continues to next line
                self.setFormat(
                    start_idx, len(text) - start_idx, self.multiLineCommentFormat
                )
                self.setCurrentBlockState(1)
                break
            else:
                length = end_idx - start_idx + end_match.capturedLength()
                self.setFormat(start_idx, length, self.multiLineCommentFormat)
                start_match = self.commentStart.match(text, start_idx + length)
                start_idx = start_match.capturedStart()


# ===================================================
#              Autocomplete Editor
# ===================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor: "AutoCompleteTextEdit" = editor
        self.setObjectName("LineNumberArea")

    def sizeHint(self):
        return QSize(self.code_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.code_editor.lineNumberAreaPaintEvent(event)


class AutoCompleteTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._completer = None

        # line number area
        self.lineNumberArea = LineNumberArea(self)
        font = self.font()
        font.setFamily("Consolas")
        font.setPointSize(12)
        self.setFont(font)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    # ---- LINE NUMBER AREA ----
    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 8 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect: QRect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        bg_palette_color = self.palette().color(self.backgroundRole())

        brightness = (
            bg_palette_color.red() + bg_palette_color.green() + bg_palette_color.blue()
        ) / 3
        is_dark = brightness < 128

        if is_dark:
            bg_color = QColor(30, 30, 30)
            fg_color = QColor(150, 150, 150)
        else:
            bg_color = QColor(245, 245, 245)
            fg_color = QColor(100, 100, 100)

        painter.fillRect(event.rect(), bg_color)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(fg_color)
                painter.drawText(
                    0,
                    top,
                    self.lineNumberArea.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            bg_palette_color = self.palette().color(self.backgroundRole())
            brightness = (
                bg_palette_color.red()
                + bg_palette_color.green()
                + bg_palette_color.blue()
            ) / 3
            is_dark = brightness < 128

            # Select line color based on theme
            lineColor = QColor(45, 45, 48) if is_dark else QColor(230, 240, 255)
            selection.format.setBackground(lineColor)
            # selection.format.setProperty(QTextEdit.ExtraSelection.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    # ---- AUTOCOMPLETE ----
    def setCompleter(self, completer: QCompleter):
        if self._completer:
            self._completer.activated.disconnect()
        self._completer = completer
        completer.setWidget(self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated.connect(self.insertCompletion)

    def completer(self):
        return self._completer

    def insertCompletion(self, completion: str):
        tc = self.textCursor()
        prefix = self.textUnderCursor()
        for _ in range(len(prefix)):
            tc.deletePreviousChar()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self) -> str:
        tc = self.textCursor()
        tc.select(tc.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, e):
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                e.ignore()
                return
            if e.key() == Qt.Key_Escape:
                self._completer.popup().hide()
                e.ignore()
                return

        super().keyPressEvent(e)

        if not self._completer:
            return

        prefix = self.textUnderCursor()
        if len(prefix) < 1:
            self._completer.popup().hide()
            return

        self._completer.setCompletionPrefix(prefix)
        cr = self.cursorRect()
        cr.setWidth(
            self._completer.popup().sizeHintForColumn(0)
            + self._completer.popup().verticalScrollBar().sizeHint().width()
        )
        self._completer.complete(cr)

    def toggle_comment(self):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        has_selection = cursor.hasSelection()

        cursor.setPosition(start)
        start_block = cursor.blockNumber()

        cursor.setPosition(end)
        end_block = cursor.blockNumber()

        if has_selection and cursor.positionInBlock() == 0 and end_block > start_block:
            end_block -= 1

        all_commented = True
        lines_to_toggle = []

        for b_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(b_num)
            text = block.text().strip()
            if text:
                if not text.startswith("//"):
                    all_commented = False
            lines_to_toggle.append((b_num, block.text()))

        cursor.beginEditBlock()

        for b_num, line_text in lines_to_toggle:
            block = self.document().findBlockByNumber(b_num)
            cursor.setPosition(block.position())

            if all_commented:
                text = block.text()
                if text.strip().startswith("//"):
                    idx = text.find("//")
                    if idx != -1:
                        len_to_remove = 2
                        if idx + 2 < len(text) and text[idx + 2] == " ":
                            len_to_remove = 3
                        cursor.setPosition(block.position() + idx)
                        cursor.movePosition(
                            QTextCursor.Right, QTextCursor.KeepAnchor, len_to_remove
                        )
                        cursor.removeSelectedText()
            else:
                text = block.text()
                idx = len(text) - len(text.lstrip())
                cursor.setPosition(block.position() + idx)
                cursor.insertText("// ")

        cursor.endEditBlock()

        start_pos = self.document().findBlockByNumber(start_block).position()
        end_block_obj = self.document().findBlockByNumber(end_block)
        end_pos = end_block_obj.position() + len(end_block_obj.text())

        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())

        tc = self.textCursor()
        if not (
            tc.hasSelection()
            and tc.selectionStart() <= cursor.position() <= tc.selectionEnd()
        ):
            self.setTextCursor(cursor)
            tc = cursor

        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "edit_board_fen"):
            parent_widget = parent_widget.parentWidget()

        if parent_widget:
            fen_info = parent_widget.find_fen_at_cursor(tc)
            action = menu.addAction(
                "Edit FEN Visually..." if fen_info else "Insert FEN..."
            )
            action.setIcon(qta.icon("fa5s.chess-board"))
            action.triggered.connect(parent_widget.edit_board_fen)
            menu.addSeparator()

        action_comment = menu.addAction("Toggle Comment")
        action_comment.setIcon(qta.icon("fa5s.comment-slash"))
        action_comment.setShortcut("Ctrl+/")
        action_comment.triggered.connect(self.toggle_comment)

        menu.exec_(event.globalPos())

    def mouseDoubleClickEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        parent_widget = self.parentWidget()
        while parent_widget and not hasattr(parent_widget, "edit_board_fen"):
            parent_widget = parent_widget.parentWidget()

        if parent_widget:
            fen_info = parent_widget.find_fen_at_cursor(cursor)
            if fen_info:
                # Move cursor to double-click position and trigger edit
                self.setTextCursor(cursor)
                parent_widget.edit_board_fen()
                event.accept()
                return

        super().mouseDoubleClickEvent(event)


# ===================================================
#                Main Widget / UI
# ===================================================
CQL_KEYWORDS_FOR_COMPLETER = [
    "abs",
    "Aa",
    "and",
    "ascii",
    "assert",
    "atomic",
    "between",
    "black",
    "btm",
    "castle",
    "check",
    "child",
    "comment",
    "connectedpawns",
    "consecutivemoves",
    "countmoves",
    "currentmove",
    "currentposition",
    "currenttransform",
    "dark",
    "date",
    "depth",
    "dictionary",
    "distance",
    "doubledpawns",
    "down",
    "echo",
    "eco",
    "elo",
    "event",
    "eventdate",
    "false",
    "fen",
    "file",
    "find",
    "flip",
    "flipcolor",
    "fliphorizontal",
    "flipvertical",
    "from",
    "function",
    "gamenumber",
    "hascomment",
    "idealmate",
    "idealstalemate",
    "if",
    "in",
    "indexof",
    "initial",
    "initialposition",
    "int",
    "isbound",
    "isolatedpawns",
    "isunbound",
    "lastgamenumber",
    "lca",
    "legal",
    "left",
    "pseudolegal",
    "light",
    "local",
    "loop",
    "lowercase",
    "mainline",
    "makesquare",
    "mate",
    "message",
    "modelmate",
    "modelstalemate",
    "movenumber",
    "northeast",
    "northwest",
    "not",
    "notransform",
    "nullmove",
    "o-o",
    "o-o-o",
    "or",
    "originalcomment",
    "parent",
    "passedpawns",
    "path",
    "pathcount",
    "pathcountunfocused",
    "pathlastposition",
    "pathstatus",
    "persistent",
    "piece",
    "piecename",
    "pieceid",
    "pin",
    "player",
    "ply",
    "position",
    "positionid",
    "power",
    "primary",
    "pseudolegal",
    "puremate",
    "purestalemate",
    "rank",
    "ray",
    "readfile",
    "removecomment",
    "result",
    "reversecolor",
    "right",
    "rotate45",
    "rotate90",
    "secondary",
    "shift",
    "shifthorizontal",
    "shiftvertical",
    "sidetomove",
    "site",
    "sort",
    "sqrt",
    "square",
    "stalemate",
    "tag",
    "terminal",
    "to",
    "true",
    "try",
    "type",
    "typename",
    "unbind",
    "up",
    "uppercase",
    "variation",
    "virtualmainline",
    "while",
    "white",
    "wtm",
    "year",
    # --- CQLi Specific ---
    "cqlbegin",
    "cqlend",
    "imagine",
    "reachableposition",
    "replace",
    "key",
    "speculative",
    "tourney_edition",
    "tourney_name",
    "tourney_year",
    "tourney_year_end",
    "tourney_year_part",
    "distinction",
]


class CqlEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CQL Query Editor")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # --- Toolbar ---
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(5, 5, 5, 5)

        btn_edit_fen = QPushButton(" Edit/Insert Board FEN")
        btn_edit_fen.setIcon(qta.icon("fa5s.chess-board"))
        btn_edit_fen.setToolTip(
            "Visual Chessboard Editor (double-click inside FEN to edit, or click here to insert/edit)"
        )
        btn_edit_fen.clicked.connect(self.edit_board_fen)

        btn_toggle_comment = QPushButton(" Toggle Comment")
        btn_toggle_comment.setIcon(qta.icon("fa5s.comment-slash"))
        btn_toggle_comment.setToolTip("Toggle comment on selected lines (Ctrl+/)")
        btn_toggle_comment.clicked.connect(self.toggle_comment)

        toolbar_layout.addWidget(btn_edit_fen)
        toolbar_layout.addWidget(btn_toggle_comment)
        toolbar_layout.addStretch()
        root.addLayout(toolbar_layout)

        # --- Editor
        self.editor = AutoCompleteTextEdit(self)
        root.addWidget(self.editor, 1)

        # --- Highlighter (theme-aware)
        self.highlighter = SqlHighlighter(self.editor.document(), theme="dark")

        # --- Completer
        completer = QCompleter(sorted(CQL_KEYWORDS_FOR_COMPLETER, key=str.lower))
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.editor.setCompleter(completer)

        # --- Keyboard Shortcut for toggling comments ---
        self.comment_shortcut = QShortcut(QKeySequence("Ctrl+/"), self)
        self.comment_shortcut.activated.connect(self.toggle_comment)

    def edit_board_fen(self):
        from dialogs.board_editor import BoardEditorDlg

        cursor = self.editor.textCursor()
        fen_info = self.find_fen_at_cursor(cursor)

        if fen_info:
            start, end, fen_string = fen_info
            # Open board editor with this FEN
            dlg = BoardEditorDlg(self, initial_fen=fen_string)
            if dlg.exec_() == QDialog.Accepted:
                new_fen = dlg.get_fen()
                document_text = self.editor.toPlainText()
                quote = document_text[start]  # should be ' or "

                # Replace the old quoted FEN
                new_cursor = self.editor.textCursor()
                new_cursor.setPosition(start)
                new_cursor.setPosition(end, QTextCursor.KeepAnchor)
                new_cursor.insertText(f"{quote}{new_fen}{quote}")
        else:
            # Open board editor with starting FEN (None uses default start position)
            dlg = BoardEditorDlg(self, initial_fen=None)
            if dlg.exec_() == QDialog.Accepted:
                new_fen = dlg.get_fen()
                # Insert fen "..." at the current cursor position
                self.editor.insertPlainText(f'fen "{new_fen}"')

    def find_fen_at_cursor(self, cursor):
        text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()

        # Matches double quotes and single quotes
        pattern = re.compile(
            r'(?:"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\')'
        )
        for match in pattern.finditer(text):
            start = match.start()
            end = match.end()
            if start <= pos_in_block <= end:
                content = match.group(1) or match.group(2) or ""
                # A FEN has 8 ranks separated by slashes
                if content.count("/") >= 7:
                    # Validate partial FEN
                    test_fen = content
                    if content.count(" ") == 0:
                        test_fen += " w - - 0 1"
                    try:
                        import chess

                        chess.Board(test_fen)
                        block_start = cursor.block().position()
                        return (block_start + start, block_start + end, content)
                    except ValueError:
                        pass
        return None

    def setTheme(self, theme: str):
        self.highlighter.setTheme(theme)

        # Adjust editor background and text color based on theme
        if theme == "dark":
            self.editor.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #1E1E1E;
                    color: #D4D4D4;
                    border: 1px solid #3E3E3E;
                }
            """
            )
        else:
            self.editor.setStyleSheet(
                """
                QPlainTextEdit {
                    background-color: #FFFFFF;
                    color: #000000;
                    border: 1px solid #CCCCCC;
                }
            """
            )

    def toggle_comment(self):
        self.editor.toggle_comment()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = CqlEditorWidget()
    editor.show()
    sys.exit(app.exec_())
