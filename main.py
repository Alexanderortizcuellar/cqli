import json
import sys
import os
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QAction,
    QDockWidget,
    QTextEdit,
    QToolBar,
    QStatusBar,
    QDialog,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QProgressDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
    QLabel,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QFile, pyqtSignal
from PyQt5.QtGui import QIcon
import qtawesome as qta

# Import core modules and widgets
from core.process import CQLProcess
from core.indexer import PGNIndexerProcess
from core.styles import LIGHT_QSS, DARK_QSS, LOG_LIGHT_CSS, LOG_DARK_CSS
from widgets.cql_editor import CqlEditorWidget
from widgets.game_list_table import GameListTableWidget
from widgets.game_explorer_widget import GameExplorerWidget


def fa_icon(*names, color="#1F2937"):
    """Helper to safely get QtAwesome icon with fallback."""
    for n in names:
        try:
            return qta.icon(n, color=color)
        except Exception:
            continue
    return qta.icon("fa5s.question")  # fallback icon


class QueryTemplatesDialog(QDialog):
    createQueryRequest = pyqtSignal(str)
    overwriteQueryRequest = pyqtSignal(int)
    templateSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Templates")
        self.resize(400, 500)

        # Detect dark mode from parent
        self.dark_mode = False
        if parent and hasattr(parent, "dark_mode"):
            self.dark_mode = parent.dark_mode

        layout = QVBoxLayout(self)

        # --- List Widget for Templates ---
        self.template_list = QListWidget(self)
        self.template_list.itemClicked.connect(
            lambda: self.templateSelected.emit(self.get_current_template())
        )
        self.template_list.currentRowChanged.connect(self.update_description)
        layout.addWidget(self.template_list)

        # --- Description Label/Panel ---
        self.desc_label = QLabel("Select a template to view details.", self)
        self.desc_label.setWordWrap(True)
        if self.dark_mode:
            self.desc_label.setStyleSheet(
                "color: #bababa; font-style: italic; margin-bottom: 5px; padding: 6px; background: #262421; border-radius: 4px; border: 1px solid #3d3a37;"
            )
        else:
            self.desc_label.setStyleSheet(
                "color: #666; font-style: italic; margin-bottom: 5px; padding: 6px; background: #f5f5f5; border-radius: 4px; border: 1px solid #e0e0e0;"
            )
        layout.addWidget(self.desc_label)

        # --- Input Fields ---
        input_form = QFormLayout()

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Enter new template name...")
        input_form.addRow("Name:", self.input_field)

        self.desc_field = QLineEdit(self)
        self.desc_field.setPlaceholderText("Enter template description...")
        input_form.addRow("Description:", self.desc_field)

        layout.addLayout(input_form)

        # --- Add, Overwrite & Delete Buttons ---
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Template", self)
        add_btn.setIcon(fa_icon("fa5s.plus", "fa.plus"))
        add_btn.clicked.connect(
            lambda: self.createQueryRequest.emit(self.input_field.text())
        )

        overwrite_btn = QPushButton("Overwrite Selected", self)
        overwrite_btn.setIcon(fa_icon("fa5s.save", "fa.save"))
        overwrite_btn.clicked.connect(self.on_overwrite_clicked)

        delete_btn = QPushButton("Delete Selected", self)
        delete_btn.setIcon(fa_icon("fa5s.trash", "fa.trash"))
        delete_btn.clicked.connect(self.delete_selected)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(overwrite_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        # --- Close Button ---
        close_btn = QPushButton("Close", self)
        close_btn.setIcon(fa_icon("fa5s.times", "fa.close"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.templates = []
        self.load_templates()

    def get_current_template(self):
        query_index = self.template_list.currentIndex().row()
        if 0 <= query_index < len(self.templates):
            return self.templates[query_index]["query"]
        return ""

    def update_description(self, row):
        if 0 <= row < len(self.templates):
            t = self.templates[row]
            desc = t.get("description", "No description available.")
            if not desc:
                desc = "No description available."
            self.desc_label.setText(desc)
            self.input_field.setText(t.get("name", ""))
            self.desc_field.setText(t.get("description", ""))
        else:
            self.desc_label.setText("Select a template to view details.")
            self.input_field.clear()
            self.desc_field.clear()

    def load_templates(self):
        file = QFile("data/queries.json")
        if file.exists():
            try:
                with open("data/queries.json", "r") as f:
                    self.templates = json.load(f)
                    self.template_list.clear()
                    for t in self.templates:
                        item = QListWidgetItem(t["name"], self.template_list)
                        desc = t.get("description", "")
                        if desc:
                            item.setToolTip(desc)
            except Exception as e:
                print("Error loading templates.", e)

    def add_template(self, query):
        text = self.input_field.text().strip()
        desc = self.desc_field.text().strip()
        if text:
            # Check if template with the same name already exists
            existing_idx = -1
            for idx, t in enumerate(self.templates):
                if t["name"].lower() == text.lower():
                    existing_idx = idx
                    break

            if existing_idx != -1:
                reply = QMessageBox.question(
                    self,
                    "Overwrite Template",
                    f"A template named '{text}' already exists. Do you want to overwrite it with the current query and description?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self.templates[existing_idx]["description"] = desc
                    self.templates[existing_idx]["query"] = query
                    try:
                        with open("data/queries.json", "w") as f:
                            json.dump(self.templates, f, indent=4)
                        self.load_templates()
                        self.input_field.clear()
                        self.desc_field.clear()
                    except Exception as e:
                        print("Error saving template:", e)
                    return
                else:
                    return

            self.templates.append({"name": text, "description": desc, "query": query})
            try:
                with open("data/queries.json", "w") as f:
                    json.dump(self.templates, f, indent=4)
                self.load_templates()
                self.input_field.clear()
                self.desc_field.clear()
            except Exception as e:
                print("Error saving template:", e)

    def on_overwrite_clicked(self):
        index = self.template_list.currentIndex().row()
        if 0 <= index < len(self.templates):
            self.overwriteQueryRequest.emit(index)
        else:
            QMessageBox.warning(
                self, "No Selection", "Please select a template to overwrite."
            )

    def overwrite_template(self, idx, query):
        if 0 <= idx < len(self.templates):
            text = self.input_field.text().strip()
            desc = self.desc_field.text().strip()
            if not text:
                QMessageBox.warning(
                    self, "Invalid Name", "Template name cannot be empty."
                )
                return

            old_name = self.templates[idx]["name"]
            reply = QMessageBox.question(
                self,
                "Overwrite Template",
                f"Are you sure you want to overwrite the selected template '{old_name}' with the current query, name, and description?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.templates[idx]["name"] = text
                self.templates[idx]["description"] = desc
                self.templates[idx]["query"] = query
                try:
                    with open("data/queries.json", "w") as f:
                        json.dump(self.templates, f, indent=4)
                    self.load_templates()
                    self.template_list.setCurrentRow(idx)
                except Exception as e:
                    print("Error overwriting template:", e)

    def delete_selected(self):
        index = self.template_list.currentIndex().row()
        if 0 <= index < len(self.templates):
            self.templates.pop(index)
            try:
                with open("data/queries.json", "w") as f:
                    json.dump(self.templates, f, indent=4)
                self.load_templates()
                self.desc_label.setText("Select a template to view details.")
            except Exception as e:
                print("Error deleting template:", e)


class ChessboardDialog(QDialog):
    def __init__(self, game_info: dict, parent=None, html_style=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Chessboard Explorer")
        self.resize(1100, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = GameExplorerWidget(self, html_style=html_style)
        layout.addWidget(self.browser)
        self.browser.load_game(game_info)

    def closeEvent(self, event):
        self.browser.closeEvent(event)
        event.accept()


class ChessCQLiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess CQLi Query Tool")
        self.setWindowIcon(QIcon("images/cql_logo.png"))
        self.resize(1200, 800)
        self.dark_mode = False

        self.pgnfilename = None
        self.game_count = 0
        self.db_game_count = 0
        self.last_query_matches = 0

        # Initialize Query Process
        self.cql = CQLProcess(self)

        # Build UI
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_central_table()
        self._create_docks()
        self._wire_view_menu_toggles()

        # Status bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        # Save default dock layout
        self.default_state = self.saveState()

        # Set default styles
        self.setStyleSheet(LIGHT_QSS)
        self.log_panel.document().setDefaultStyleSheet(LOG_LIGHT_CSS)

        self.results_table.loadFinished.connect(self.on_load_finished)

        self.cql.errorReceived.connect(self.on_error_received)
        self.cql.statsReceived.connect(self.on_info_received)
        self.cql.messageReceived.connect(self.on_message_received)
        self.cql.finishedSuccessfully.connect(self.on_cql_success)
        self.cql.finishedExecution.connect(self.on_cql_finished)

    def on_info_received(self, stats: dict):
        self.last_query_matches = stats.get("numbermatches", 0)
        numbermatches = self.last_query_matches
        total_games = stats.get("totalgames", self.db_game_count)
        self.status_bar.showMessage(f"{numbermatches} matches of {total_games} games")
        self.log_panel.append(
            f"<span class='blue'>Search finished: {numbermatches} matches found.</span>"
        )

    def on_error_received(self, error: str):
        self.log_panel.insertHtml(f"<span class='error'>{error}</span><br>")

    def on_message_received(self, message: str):
        self.log_panel.insertHtml(f"<span class='gray'>{message}</span><br>")

    def show_progress(self):
        self.progress_dlg = QProgressDialog(
            "Searching games with CQLi...",
            "Cancel",
            0,
            self.db_game_count,
            self,
            Qt.WindowCloseButtonHint,
        )
        self.progress_dlg.setWindowTitle("Query Executing...")

        try:
            self.cql.progressUpdated.disconnect()
        except TypeError:
            pass

        self.cql.progressUpdated.connect(self.progress_dlg.setValue)
        self.progress_dlg.canceled.connect(self.cql.terminate)

        self.progress_dlg.setWindowModality(Qt.ApplicationModal)
        self.progress_dlg.setValue(0)
        self.progress_dlg.exec_()

    # ----- Actions with Icons -----
    def _create_actions(self):
        # File
        self.act_open_pgn = QAction(
            fa_icon("fa5s.folder-open", "fa.folder-open"), "Open PGN", self
        )
        self.act_open_pgn.setShortcut("Ctrl+O")
        self.act_open_pgn.setStatusTip("Open a PGN database file")
        self.act_open_pgn.triggered.connect(self.open_pgn_file)

        self.act_save_query = QAction(
            fa_icon("fa5s.save", "fa.save"), "Save Query", self
        )
        self.act_save_query.setShortcut("Ctrl+S")
        self.act_save_query.setStatusTip("Save current query script")
        self.act_save_query.triggered.connect(self.save_query)

        self.act_export_results = QAction(
            fa_icon("fa5s.file-export", "fa.upload"), "Export Results", self
        )
        self.act_export_results.setShortcut("Ctrl+Shift+E")
        self.act_export_results.setStatusTip("Export search results to PGN")
        self.act_export_results.triggered.connect(self.export_results)

        # Edit (Placeholders)
        self.act_undo = QAction(fa_icon("fa5s.undo", "fa.undo"), "Undo", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.triggered.connect(lambda: self.log_panel.append("Undo clicked"))

        self.act_redo = QAction(fa_icon("fa5s.redo", "fa.repeat"), "Redo", self)
        self.act_redo.setShortcut("Ctrl+Y")
        self.act_redo.triggered.connect(lambda: self.log_panel.append("Redo clicked"))

        self.act_clear_logs = QAction(
            fa_icon("fa5s.broom", "fa.eraser"), "Clear Logs", self
        )
        self.act_clear_logs.setStatusTip("Clear the logs panel output")
        self.act_clear_logs.triggered.connect(self.clear_logs)

        # Tools
        self.act_templates = QAction(
            fa_icon("fa5s.list", "fa.list"), "Query Templates…", self
        )
        self.act_templates.setShortcut("Ctrl+T")
        self.act_templates.triggered.connect(self.show_query_templates)

        self.act_engine_config = QAction(
            fa_icon("fa5s.cog", "fa.cog"), "Engine Configuration…", self
        )
        self.act_engine_config.setStatusTip("Configure chess engine options")
        self.act_engine_config.triggered.connect(self.show_engine_config)

        # View
        self.act_theme = QAction(self._theme_icon(), "Dark Mode", self)
        self.act_theme.setCheckable(True)
        self.act_theme.setShortcut("Ctrl+D")
        self.act_theme.setStatusTip("Toggle Dark/Light theme")
        self.act_theme.triggered.connect(self.toggle_theme)

        self.act_reset_layout = QAction(
            fa_icon("fa5s.window-restore", "fa.window-restore"), "Reset Layout", self
        )
        self.act_reset_layout.setStatusTip("Restore default dock positions")
        self.act_reset_layout.triggered.connect(self.reset_layout)

        self.act_configure_columns = QAction(
            fa_icon("fa5s.columns", "fa.columns"), "Configure Columns…", self
        )
        self.act_configure_columns.setStatusTip(
            "Show/hide and reorder result table columns"
        )
        self.act_configure_columns.triggered.connect(
            lambda: self.results_table.configure_columns()
        )

        # Toolbar
        self.act_run = QAction(fa_icon("fa5s.play", "fa.play"), "Run Query", self)
        self.act_run.setShortcut("F5")
        self.act_run.triggered.connect(self.run_query)

        self.act_clear = QAction(
            fa_icon("fa5s.trash", "fa.trash"), "Clear Results", self
        )
        self.act_clear.setShortcut("Ctrl+L")
        self.act_clear.triggered.connect(self.clear_results_placeholder)

        self.act_stop = QAction(fa_icon("fa5s.stop", "fa.stop"), "Stop", self)
        self.act_stop.setEnabled(False)
        self.act_stop.triggered.connect(self.cql.terminate)

    # ----- Menus -----
    def _create_menus(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.act_open_pgn)

        self.recent_menu = file_menu.addMenu("Open Recent")
        self.recent_menu.setIcon(fa_icon("fa5s.history", "fa.history"))
        self.update_recent_menu()

        file_menu.addAction(self.act_save_query)
        file_menu.addAction(self.act_export_results)

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_clear_logs)

        self.view_menu = menu_bar.addMenu("View")
        self.view_menu.addAction(self.act_configure_columns)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.act_theme)
        self.view_menu.addAction(self.act_reset_layout)

        tools_menu = menu_bar.addMenu("Tools")
        tools_menu.addAction(self.act_templates)
        tools_menu.addAction(self.act_engine_config)

    # ----- Toolbar -----
    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setObjectName("MainToolbar")
        toolbar.setMovable(True)
        toolbar.addAction(self.act_run)
        toolbar.addAction(self.act_stop)
        toolbar.addSeparator()

        # Checkbox for removing comments
        self.cb_remove_comments = QCheckBox("Remove Comments")
        self.cb_remove_comments.setToolTip(
            "Suppress all comments (including variations/original comments) in the query results"
        )
        toolbar.addWidget(self.cb_remove_comments)

        # Checkbox for silent mode (suppressing CQL comments)
        self.cb_silent_mode = QCheckBox("Suppress CQL Comments")
        self.cb_silent_mode.setToolTip(
            "Suppress matching position comments ({CQL}) automatically added by CQLi"
        )
        toolbar.addWidget(self.cb_silent_mode)

        toolbar.addSeparator()
        toolbar.addAction(self.act_clear)
        self.addToolBar(toolbar)

    def _create_central_table(self):
        self.main_container = QWidget()
        self.main_container_layout = QVBoxLayout()
        self.main_container_layout.setContentsMargins(10, 10, 10, 10)

        self.results_table = GameListTableWidget()

        self.main_container.setLayout(self.main_container_layout)
        self.main_container_layout.addWidget(self.results_table)
        self.setCentralWidget(self.main_container)

        self.results_table.gameSelected.connect(self.show_chessboard_dialog)

    # ----- Docks (CQL editor + Logs) -----
    def _create_docks(self):
        # CQL Editor Dock
        self.cql_dock = QDockWidget("CQL Editor", self)
        self.cql_dock.setObjectName("CQLDock")
        self.cql_editor = CqlEditorWidget()
        self.cql_dock.setWidget(self.cql_editor)
        self.cql_dock.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(Qt.LeftDockWidgetArea, self.cql_dock)

        # Logs Dock
        self.log_dock = QDockWidget("Logs", self)
        self.log_dock.setObjectName("LogsDock")
        self.log_panel = QTextEdit(self)
        self.log_panel.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_panel.customContextMenuRequested.connect(
            self._on_log_panel_context_menu
        )
        self.log_panel.insertHtml(
            "<span class='success'>Welcome to Chess CQLi Query Tool!</span><br>"
        )
        self.log_panel.setReadOnly(True)
        self.log_dock.setWidget(self.log_panel)
        self.log_dock.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

    def _wire_view_menu_toggles(self):
        # Add toggle actions for docks into View menu
        self.cql_toggle = self.cql_dock.toggleViewAction()
        self.cql_toggle.setIcon(fa_icon("fa5s.code", "fa.code"))
        self.view_menu.insertAction(
            self.view_menu.actions()[0] if self.view_menu.actions() else None,
            self.cql_toggle,
        )

        self.log_toggle = self.log_dock.toggleViewAction()
        self.log_toggle.setIcon(fa_icon("fa5s.terminal", "fa.terminal"))
        self.view_menu.insertAction(
            self.view_menu.actions()[1] if len(self.view_menu.actions()) > 1 else None,
            self.log_toggle,
        )

    # ----- View Actions -----
    def _theme_icon(self) -> QIcon:
        return (
            fa_icon("fa5s.moon", "fa.moon-o")
            if not self.dark_mode
            else fa_icon("fa5s.sun", "fa.sun-o")
        )

    def toggle_theme(self, checked: bool):
        self.dark_mode = checked
        if self.dark_mode:
            self.setStyleSheet(DARK_QSS)
            self.log_panel.document().setDefaultStyleSheet(LOG_DARK_CSS)
            self.cql_editor.setTheme("dark")
        else:
            self.setStyleSheet(LIGHT_QSS)
            self.log_panel.document().setDefaultStyleSheet(LOG_LIGHT_CSS)
            self.cql_editor.setTheme("light")

        self.act_theme.setIcon(self._theme_icon())
        self.act_theme.setText("Dark Mode" if not self.dark_mode else "Light Mode")
        self._update_icons()

    def _update_icons(self):
        icon_color = "#E5E7EB" if self.dark_mode else "#1F2937"

        self.act_run.setIcon(qta.icon("fa5s.play", color=icon_color))
        self.act_clear.setIcon(qta.icon("fa5s.trash", color=icon_color))
        self.act_reset_layout.setIcon(qta.icon("fa5s.window-restore", color=icon_color))
        self.act_open_pgn.setIcon(qta.icon("fa5s.folder-open", color=icon_color))
        self.act_save_query.setIcon(qta.icon("fa5s.save", color=icon_color))
        self.act_export_results.setIcon(qta.icon("fa5s.file-export", color=icon_color))
        self.act_redo.setIcon(qta.icon("fa5s.redo", color=icon_color))
        self.act_undo.setIcon(qta.icon("fa5s.undo", color=icon_color))
        self.cql_toggle.setIcon(qta.icon("fa5s.code", color=icon_color))
        self.log_toggle.setIcon(qta.icon("fa5s.terminal", color=icon_color))
        self.act_theme.setIcon(
            qta.icon(
                "fa5s.moon" if not self.dark_mode else "fa5s.sun", color=icon_color
            )
        )
        self.act_templates.setIcon(qta.icon("fa5s.list", color=icon_color))
        self.recent_menu.setIcon(qta.icon("fa5s.history", color=icon_color))
        self.act_engine_config.setIcon(qta.icon("fa5s.cog", color=icon_color))
        self.act_configure_columns.setIcon(qta.icon("fa5s.columns", color=icon_color))
        self.act_clear_logs.setIcon(qta.icon("fa5s.broom", color=icon_color))

    def reset_layout(self):
        self.restoreState(self.default_state)
        self._wire_view_menu_toggles()

    def show_query_templates(self):
        dlg = QueryTemplatesDialog(self)
        dlg.createQueryRequest.connect(
            lambda: dlg.add_template(self.cql_editor.editor.toPlainText())
        )
        dlg.overwriteQueryRequest.connect(
            lambda idx: dlg.overwrite_template(
                idx, self.cql_editor.editor.toPlainText()
            )
        )
        dlg.templateSelected.connect(
            lambda template: self.cql_editor.editor.setPlainText(template)
        )
        dlg.exec_()

    def show_engine_config(self):
        from dialogs.engine_dlg import EngineConfigDialog

        dlg = EngineConfigDialog(self)
        dlg.exec_()

    def load_recent_files(self):
        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Config")
        recent = settings.value("recent_pgns", [])
        if recent is None:
            recent = []
        elif isinstance(recent, str):
            recent = [recent]
        else:
            try:
                recent = list(recent)
            except Exception:
                recent = []

        valid_recent = []
        for path in recent:
            if (
                path
                and isinstance(path, str)
                and os.path.exists(path)
                and path not in valid_recent
            ):
                valid_recent.append(path)
        return valid_recent[:10]

    def add_recent_file(self, filename):
        if not filename:
            return
        filename = os.path.abspath(filename)
        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Config")
        recent = settings.value("recent_pgns", [])
        if recent is None:
            recent = []
        elif isinstance(recent, str):
            recent = [recent]
        else:
            try:
                recent = list(recent)
            except Exception:
                recent = []

        if filename in recent:
            recent.remove(filename)
        recent.insert(0, filename)

        settings.setValue("recent_pgns", recent[:10])
        self.update_recent_menu()

    def remove_recent_file(self, filename):
        if not filename:
            return
        filename = os.path.abspath(filename)
        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Config")
        recent = settings.value("recent_pgns", [])
        if recent is None:
            recent = []
        elif isinstance(recent, str):
            recent = [recent]
        else:
            try:
                recent = list(recent)
            except Exception:
                recent = []

        if filename in recent:
            recent.remove(filename)
        settings.setValue("recent_pgns", recent)
        self.update_recent_menu()

    def update_recent_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        recent = self.load_recent_files()
        if not recent:
            no_recent_action = QAction("No Recent Files", self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
            return

        for path in recent:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self.load_pgn_file(p))
            self.recent_menu.addAction(action)

    def show_chessboard_dialog(self, game: dict):
        ChessboardDialog(game, self, html_style=self.dark_mode).exec_()

    def run_query(self):
        if not self.pgnfilename:
            QMessageBox.warning(
                self,
                "Missing PGN File",
                "Please open an input PGN file before running the query.",
            )
            return

        query_text = self.cql_editor.editor.toPlainText().strip()
        if not query_text:
            QMessageBox.warning(
                self,
                "Empty Query",
                "Please enter a CQL query in the editor first.",
            )
            return

        # Delete old output files to avoid stale results
        self.results_table.clear()
        for f in ["temp_out.pgn", "temp_out.pgn.db"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Could not remove temporary file {f}: {e}")

        self.last_query_matches = 0
        self.log_panel.append("<span class='purple'>Starting CQLi search...</span>")
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.cql.search(
            query_text,
            self.pgnfilename,
            self.db_game_count,
            elide_comments=self.cb_remove_comments.isChecked(),
            silent_mode=self.cb_silent_mode.isChecked(),
        )
        self.show_progress()

    def open_pgn_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if filename:
            self.load_pgn_file(filename)

    def load_pgn_file(self, filename):
        if not filename or not os.path.exists(filename):
            QMessageBox.warning(
                self, "File Not Found", f"The PGN file '{filename}' does not exist."
            )
            self.remove_recent_file(filename)
            return

        self.pgnfilename = filename
        self.add_recent_file(filename)
        db_path = filename + ".db"

        # Check if SQLite index database already exists next to it and is newer than the PGN file
        if os.path.exists(db_path) and os.path.getmtime(db_path) >= os.path.getmtime(
            filename
        ):
            self.status_bar.showMessage(
                f"Loading indexed PGN: {os.path.basename(filename)}..."
            )
            self.results_table.load_db(db_path, filename)
            return

        self.status_bar.showMessage(
            f"Indexing database: {os.path.basename(filename)}... Please wait..."
        )
        self.log_panel.append(f"<span class='blue'>Indexing: {filename}</span>")
        self.act_run.setEnabled(False)

        self.indexer = PGNIndexerProcess(self)
        self.indexer.finishedSuccessfully.connect(self.on_indexing_finished)
        self.indexer.errorOccurred.connect(self.on_indexing_error)
        self.indexer.progressMessage.connect(self.log_panel.append)

        # Show standard loading modal
        self.index_dlg = QProgressDialog(
            "Indexing PGN file with Rust...", "Cancel", 0, 0, self
        )
        self.index_dlg.setWindowTitle("Indexing...")
        self.indexer.finished.connect(self.index_dlg.close)
        self.indexer.start()
        self.indexer.index_pgn(filename)
        self.index_dlg.exec_()

    def on_indexing_finished(self, db_path: str):
        self.log_panel.append(
            f"<span class='success'>Indexing completed successfully: {db_path}</span>"
        )
        self.results_table.load_db(db_path, self.pgnfilename)

    def on_indexing_error(self, error: str):
        self.log_panel.append(f"<span class='error'>Indexing failed: {error}</span>")
        QMessageBox.critical(
            self, "Indexing Error", f"Failed to index PGN file:\n{error}"
        )
        self.act_run.setEnabled(True)

    def on_load_finished(self, count: int):
        current_pgn = self.results_table.model.pgn_path
        if current_pgn == "temp_out.pgn":
            self.status_bar.showMessage(f"Loaded query results ({count} matches)")
            self.results_table.set_info_text(f"{count} matches found")
            self.game_count = count
        else:
            self.status_bar.showMessage(
                f"Loaded {os.path.basename(current_pgn)} ({count} games)"
            )
            self.results_table.set_info_text(f"{count} games in database")
            self.game_count = count
            self.db_game_count = count
        self.act_run.setEnabled(True)
        self.log_panel.append(
            f"<span class='success'>Database loaded. {count} games indexed. Ready for query.</span>"
        )

    def on_cql_success(self):
        if hasattr(self, "progress_dlg") and self.progress_dlg:
            self.progress_dlg.close()
            self.progress_dlg = None

        self.log_panel.append(
            "<span class='success'>CQLi compiled and completed successfully. Indexing results...</span>"
        )

        if self.last_query_matches == 0:
            self.results_table.clear()
            self.status_bar.showMessage("Query completed: 0 matches found.")
            self.results_table.set_info_text("0 matches found")
            return

        self.status_bar.showMessage("Indexing query results...")

        self.result_indexer = PGNIndexerProcess(self)
        self.result_indexer.finishedSuccessfully.connect(self.on_results_indexed)
        self.result_indexer.errorOccurred.connect(self.on_indexing_error)
        self.result_indexer.index_pgn("temp_out.pgn")

    def on_results_indexed(self, db_path: str):
        self.results_table.load_db(db_path, "temp_out.pgn")
        self.status_bar.showMessage(
            f"Query results loaded: {self.results_table.model.total_rows} matches"
        )

    def on_cql_finished(self, exitCode, exitStatus, output: str):
        if hasattr(self, "progress_dlg") and self.progress_dlg:
            self.progress_dlg.close()
            self.progress_dlg = None

        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        if exitCode != 0:
            QMessageBox.critical(
                self,
                "Query Compilation Error",
                f"CQLi failed with exit code {exitCode}.\nCheck log output for syntax details.",
            )
            self.log_panel.append(
                "<span class='error'><b>Error executing CQLi query.</b></span>"
            )

    def save_query(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Query", "", "CQL Files (*.cql)"
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.cql_editor.editor.toPlainText())
                self.status_bar.showMessage(
                    f"Saved query to {os.path.basename(filename)}"
                )
            except Exception as e:
                print("Error saving query:", e)

    def export_results(self):
        # The matches are already written to temp_out.pgn during cqli run.
        # We can just copy that file to a user specified file.
        if not os.path.exists("temp_out.pgn"):
            QMessageBox.warning(
                self, "No Results", "There are no search results to export yet."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Results PGN", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if filename:
            try:
                import shutil

                shutil.copy("temp_out.pgn", filename)
                self.status_bar.showMessage(
                    f"Exported results to {os.path.basename(filename)}"
                )
                self.log_panel.append(
                    f"<span class='success'>Exported results to {filename}</span>"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed", f"Failed to export results: {e}"
                )

    def clear_results_placeholder(self):
        self.results_table.clear()
        self.log_panel.clear()
        self.log_panel.append("Results and logs cleared.")

    def clear_logs(self):
        self.log_panel.clear()
        self.log_panel.append("<span class='success'><b>Logs cleared.</b></span>")

    def _on_log_panel_context_menu(self, pos):
        menu = self.log_panel.createStandardContextMenu()
        menu.addSeparator()
        clear_action = menu.addAction(fa_icon("fa5s.broom", "fa.eraser"), "Clear Logs")
        clear_action.triggered.connect(self.clear_logs)
        menu.exec_(self.log_panel.mapToGlobal(pos))

    def closeEvent(self, event):
        ok = QMessageBox.question(
            self,
            "Exit",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok == QMessageBox.Yes:
            # Clear results to close any open database connection
            self.results_table.clear()
            # Clean up temp files if they exist
            for f in ["temp.cql", "temp_out.pgn", "temp_out.pgn.db"]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        print(f"Error removing {f}: {e}")
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Force loading standard qtawesome font
    qta.icon("fa5s.play")
    window = ChessCQLiApp()
    window.show()
    sys.exit(app.exec_())
