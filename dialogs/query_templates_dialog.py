import os
import json
from typing import Optional, List, Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QMessageBox,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QFrame,
)
import qtawesome as qta

from widgets.cql_editor import SqlHighlighter


def fa_icon(*names, color="#1F2937"):
    """Helper to safely get QtAwesome icon with fallback."""
    for n in names:
        try:
            return qta.icon(n, color=color)
        except Exception:
            continue
    return qta.icon("fa5s.question")


class QueryTemplatesDialog(QDialog):
    """
    Advanced Categorized CQL Query & Template Manager with tree navigation,
    live searching, code preview with syntax highlighting, and preset editing.
    """

    createQueryRequest = pyqtSignal(str)
    overwriteQueryRequest = pyqtSignal(int)
    templateSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CQL Queries & Motif Templates Explorer")
        self.resize(1000, 680)

        # Detect dark mode from parent
        self.dark_mode = False
        if parent and hasattr(parent, "dark_mode"):
            self.dark_mode = parent.dark_mode

        self.queries_data: List[Dict] = []
        self._current_selected_idx: Optional[int] = None
        self._init_ui()
        self.load_templates()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Bar: Search and Category Filter
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_search = QLabel("🔍 Search:")
        lbl_search.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(lbl_search)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Filter templates by name, description, or keyword (e.g. mate, fork, bishop)..."
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.search_edit, 1)

        self.cat_combo = QComboBox()
        self.cat_combo.addItem("All Categories")
        self.cat_combo.currentIndexChanged.connect(self._apply_filter)
        top_bar.addWidget(self.cat_combo)

        main_layout.addLayout(top_bar)

        # Splitter: Left (Categories & Queries Tree) | Right (Preview & Metadata)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Left Panel: Tree Widget
        left_widget = QFrame()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Theme / Query Name", "Count / Type"])
        self.tree_widget.setColumnWidth(0, 240)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree_widget.itemDoubleClicked.connect(self._on_tree_double_clicked)
        left_layout.addWidget(self.tree_widget)

        self.lbl_stats = QLabel("Total Queries: 0")
        self.lbl_stats.setStyleSheet("color: #666; font-size: 11px;")
        left_layout.addWidget(self.lbl_stats)

        splitter.addWidget(left_widget)

        # Right Panel: Preview, Editor & Metadata
        right_widget = QFrame()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Description Card
        self.desc_group = QGroupBox("Query Details & Documentation")
        desc_layout = QVBoxLayout(self.desc_group)
        self.desc_label = QLabel(
            "Select a template from the list to view code and details."
        )
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("font-size: 12px; line-height: 1.4;")
        desc_layout.addWidget(self.desc_label)
        right_layout.addWidget(self.desc_group)

        # CQL Code Preview / Editor
        code_group = QGroupBox("CQL Script Preview")
        code_layout = QVBoxLayout(code_group)
        code_layout.setContentsMargins(6, 8, 6, 6)

        self.code_preview = QPlainTextEdit()
        self.code_preview.setFont(QFont("Consolas", 10))
        theme_str = "dark" if self.dark_mode else "light"
        self.highlighter = SqlHighlighter(self.code_preview.document(), theme=theme_str)
        code_layout.addWidget(self.code_preview)
        right_layout.addWidget(code_group, 1)

        # Metadata Editor Form (collapsible / compact)
        edit_box = QGroupBox("Template Management")
        form_layout = QFormLayout(edit_box)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(6)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Template name...")
        form_layout.addRow("Name:", self.input_name)

        self.input_cat = QComboBox()
        self.input_cat.setEditable(True)
        form_layout.addRow("Category:", self.input_cat)

        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("Description / comments...")
        form_layout.addRow("Description:", self.input_desc)

        # Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_insert = QPushButton("Insert into Editor")
        self.btn_insert.setIcon(fa_icon("fa5s.arrow-right", "fa.arrow-right"))
        self.btn_insert.setStyleSheet(
            "font-weight: bold; background-color: #2e7d32; color: white; padding: 6px 14px;"
        )
        self.btn_insert.clicked.connect(self._on_insert_clicked)
        btn_layout.addWidget(self.btn_insert)

        self.btn_add = QPushButton("Save New")
        self.btn_add.setIcon(fa_icon("fa5s.plus", "fa.plus"))
        self.btn_add.clicked.connect(self._on_add_new_clicked)
        btn_layout.addWidget(self.btn_add)

        self.btn_overwrite = QPushButton("Update Selected")
        self.btn_overwrite.setIcon(fa_icon("fa5s.save", "fa.save"))
        self.btn_overwrite.clicked.connect(self._on_overwrite_clicked)
        btn_layout.addWidget(self.btn_overwrite)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setIcon(fa_icon("fa5s.trash", "fa.trash"))
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.btn_delete)

        form_layout.addRow(btn_layout)
        right_layout.addWidget(edit_box)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 620])

        # Bottom Dialog Close Button
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setIcon(fa_icon("fa5s.times", "fa.close"))
        btn_close.clicked.connect(self.close)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

    def load_templates(self):
        path = "data/queries.json"
        if not os.path.exists(path):
            self.queries_data = []
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.queries_data = json.load(f)
        except Exception as e:
            print("Error loading queries.json:", e)
            self.queries_data = []

        # Populate category combo
        categories = sorted(
            list(set(q.get("category", "General") for q in self.queries_data))
        )
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        self.cat_combo.addItem("All Categories")
        for c in categories:
            self.cat_combo.addItem(c)
        self.cat_combo.blockSignals(False)

        self.input_cat.clear()
        for c in categories:
            self.input_cat.addItem(c)

        self._populate_tree()

    def _populate_tree(self):
        search_kw = self.search_edit.text().strip().lower()
        selected_cat = self.cat_combo.currentText()

        self.tree_widget.clear()
        category_nodes: Dict[str, QTreeWidgetItem] = {}
        total_visible = 0

        for idx, q in enumerate(self.queries_data):
            cat = q.get("category", "General")
            name = q.get("name", "Untitled")
            desc = q.get("description", "")
            query_code = q.get("query", "")

            if selected_cat != "All Categories" and cat != selected_cat:
                continue

            if search_kw:
                match_name = search_kw in name.lower()
                match_desc = search_kw in desc.lower()
                match_code = search_kw in query_code.lower()
                match_cat = search_kw in cat.lower()
                if not (match_name or match_desc or match_code or match_cat):
                    continue

            if cat not in category_nodes:
                cat_item = QTreeWidgetItem(self.tree_widget)
                cat_item.setText(0, f"📁 {cat}")
                cat_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
                cat_item.setExpanded(
                    True if search_kw or selected_cat != "All Categories" else False
                )
                category_nodes[cat] = cat_item

            item = QTreeWidgetItem(category_nodes[cat])
            item.setText(0, name)
            item.setText(1, "CQL")
            item.setData(0, Qt.UserRole, idx)
            if desc:
                item.setToolTip(0, desc)
            total_visible += 1

        # Update category count badges
        for cat, cat_item in category_nodes.items():
            child_count = cat_item.childCount()
            cat_item.setText(1, f"({child_count})")

        self.lbl_stats.setText(
            f"Showing {total_visible} of {len(self.queries_data)} queries"
        )

    def _apply_filter(self):
        self._populate_tree()

    def _on_tree_selection_changed(self):
        selected = self.tree_widget.selectedItems()
        if not selected:
            return

        item = selected[0]
        idx = item.data(0, Qt.UserRole)
        if idx is not None and 0 <= idx < len(self.queries_data):
            self._current_selected_idx = idx
            q = self.queries_data[idx]
            name = q.get("name", "")
            cat = q.get("category", "General")
            desc = q.get("description", "No description available.")
            code = q.get("query", "")

            self.desc_group.setTitle(f"Query: {name} [{cat}]")
            self.desc_label.setText(desc if desc else "No description provided.")
            self.code_preview.setPlainText(code)

            self.input_name.setText(name)
            self.input_desc.setText(desc)
            cat_idx = self.input_cat.findText(cat)
            if cat_idx >= 0:
                self.input_cat.setCurrentIndex(cat_idx)
            else:
                self.input_cat.setEditText(cat)
        else:
            self._current_selected_idx = None
            self.desc_label.setText(
                "Select a template from the list to view code and details."
            )
            self.code_preview.clear()
            self.input_name.clear()
            self.input_desc.clear()

    def _on_tree_double_clicked(self, item: QTreeWidgetItem, column: int):
        idx = item.data(0, Qt.UserRole)
        if idx is not None and 0 <= idx < len(self.queries_data):
            code = self.queries_data[idx].get("query", "")
            self.templateSelected.emit(code)
            self.accept()

    def _on_insert_clicked(self):
        code = self.code_preview.toPlainText().strip()
        if code:
            self.templateSelected.emit(code)
            self.accept()

    def _on_add_new_clicked(self):
        name = self.input_name.text().strip()
        cat = self.input_cat.currentText().strip() or "Custom / User"
        desc = self.input_desc.text().strip()
        code = self.code_preview.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a template name.")
            return
        if not code:
            QMessageBox.warning(
                self, "Missing Query", "The CQL query code cannot be empty."
            )
            return

        new_entry = {
            "category": cat,
            "name": name,
            "description": desc,
            "query": code,
        }
        self.queries_data.append(new_entry)
        self._save_queries_to_disk()
        self.load_templates()
        QMessageBox.information(self, "Saved", f"Template '{name}' added successfully.")

    def _on_overwrite_clicked(self):
        if self._current_selected_idx is None or not (
            0 <= self._current_selected_idx < len(self.queries_data)
        ):
            QMessageBox.warning(
                self, "No Selection", "Please select a template to update."
            )
            return

        name = self.input_name.text().strip()
        cat = self.input_cat.currentText().strip() or "Custom / User"
        desc = self.input_desc.text().strip()
        code = self.code_preview.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Missing Name", "Template name cannot be empty.")
            return

        self.queries_data[self._current_selected_idx] = {
            "category": cat,
            "name": name,
            "description": desc,
            "query": code,
        }
        self._save_queries_to_disk()
        self.load_templates()
        QMessageBox.information(
            self, "Updated", f"Template '{name}' updated successfully."
        )

    def _on_delete_clicked(self):
        if self._current_selected_idx is None or not (
            0 <= self._current_selected_idx < len(self.queries_data)
        ):
            QMessageBox.warning(
                self, "No Selection", "Please select a template to delete."
            )
            return

        name = self.queries_data[self._current_selected_idx].get("name", "template")
        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.queries_data.pop(self._current_selected_idx)
            self._current_selected_idx = None
            self._save_queries_to_disk()
            self.load_templates()

    def _save_queries_to_disk(self):
        try:
            with open("data/queries.json", "w", encoding="utf-8") as f:
                json.dump(self.queries_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save queries.json: {e}"
            )

    # Backwards compatibility methods
    def add_template(self, query: str):
        self.code_preview.setPlainText(query)

    def overwrite_template(self, idx: int, query: str):
        if 0 <= idx < len(self.queries_data):
            self.queries_data[idx]["query"] = query
            self._save_queries_to_disk()
            self.load_templates()
