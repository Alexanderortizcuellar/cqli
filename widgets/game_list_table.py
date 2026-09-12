import os
from typing import Optional, Dict, Any, Set, List
from collections import OrderedDict

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    pyqtSignal,
    QSettings,
    QTimer,
)
from PyQt5.QtGui import QColor, QFont

from core.backend_client import BackendClient


class GameListTableModel(QAbstractTableModel):
    """
    Virtual scrolling table model powered asynchronously by scid-mgr JSON-RPC backend.
    Maintains an LRU page chunk cache and never performs blocking operations in data().
    """

    HEADERS = [
        "ID",
        "White",
        "EloW",
        "Black",
        "EloB",
        "Result",
        "ECO",
        "Date",
        "Event",
        "Site",
        "Round",
        "Status",
    ]

    COLUMN_SORT_FIELDS = {
        0: "id",
        1: "white",
        2: "white_elo",
        3: "black",
        4: "black_elo",
        5: "result",
        6: "eco",
        7: "date",
        8: "event",
        9: "site",
        10: "round",
    }

    CHUNK_SIZE = 100
    MAX_CACHED_CHUNKS = 30  # Caps Python RAM to ~3,000 games (< 3 MB)
    stats_updated = pyqtSignal(int, int)  # total_count, cached_count

    def __init__(self, client: BackendClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.total_count = 0
        self.filters: Dict[str, Any] = {}
        self.matched_ids: List[int] = []
        self.cached_chunks: OrderedDict[int, list] = OrderedDict()
        self.in_flight_pages: Set[int] = set()
        self.sort_col: Optional[int] = None
        self.sort_asc: bool = True
        self.pgn_path: Optional[str] = None

        self.client.response_received.connect(self.on_backend_response)

    @property
    def total_rows(self) -> int:
        return self.total_count

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self.total_count

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole
    ):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            title = self.HEADERS[section]
            if self.sort_col == section:
                title += " ▲" if self.sort_asc else " ▼"
            return title
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        page = row // self.CHUNK_SIZE
        offset_in_page = row % self.CHUNK_SIZE

        chunk = self.cached_chunks.get(page)
        game_item = (
            chunk[offset_in_page] if (chunk and offset_in_page < len(chunk)) else None
        )

        if role == Qt.FontRole:
            font = QFont("Segoe UI", 10)
            col_name = self.HEADERS[col]
            if col_name in ("White", "Black", "Result"):
                font.setBold(True)
            return font

        if role == Qt.TextAlignmentRole:
            col_name = self.HEADERS[col]
            if col_name in (
                "ID",
                "EloW",
                "EloB",
                "Result",
                "Date",
                "Round",
                "ECO",
                "Status",
            ):
                return Qt.AlignCenter

        if role == Qt.DisplayRole:
            if game_item:
                return self._format_cell(game_item, col)
            return ""

        if role == Qt.ForegroundRole and game_item:
            if game_item.get("deleted"):
                return QColor("#d32f2f")  # Red for deleted games

        return None

    def _format_cell(self, g: dict, col: int) -> str:
        col_name = self.HEADERS[col]
        if col_name == "ID":
            gid = g.get("id", "")
            return str(gid + 1) if isinstance(gid, int) else str(gid)
        elif col_name == "White":
            return g.get("white", "")
        elif col_name == "EloW":
            elo = g.get("white_elo")
            return str(elo) if elo and elo > 0 else ""
        elif col_name == "Black":
            return g.get("black", "")
        elif col_name == "EloB":
            elo = g.get("black_elo")
            return str(elo) if elo and elo > 0 else ""
        elif col_name == "Result":
            return g.get("result", "")
        elif col_name == "ECO":
            return g.get("eco", "")
        elif col_name == "Date":
            return g.get("date", "")
        elif col_name == "Event":
            return g.get("event", "")
        elif col_name == "Site":
            return g.get("site", "")
        elif col_name == "Round":
            return g.get("round", "")
        elif col_name == "Status":
            status_flags = []
            if g.get("deleted"):
                status_flags.append("DEL")
            if g.get("non_standard_start"):
                status_flags.append("FEN")
            return " | ".join(status_flags) if status_flags else "OK"
        return ""

    def get_game_at(self, row: int) -> Optional[dict]:
        page = row // self.CHUNK_SIZE
        offset = row % self.CHUNK_SIZE
        chunk = self.cached_chunks.get(page)
        if chunk and offset < len(chunk):
            self.cached_chunks.move_to_end(page)
            return chunk[offset]
        return None

    def request_chunks_for_range(self, top_row: int, bottom_row: int):
        if self.total_count == 0 or not self.client.is_running():
            return

        start_page = max(0, top_row // self.CHUNK_SIZE)
        end_page = min(
            (self.total_count - 1) // self.CHUNK_SIZE,
            max(0, bottom_row // self.CHUNK_SIZE),
        )

        for page in range(start_page, end_page + 1):
            if page not in self.cached_chunks and page not in self.in_flight_pages:
                self._request_chunk(page)

    def _request_chunk(self, page: int):
        if page in self.in_flight_pages or not self.client.is_running():
            return
        self.in_flight_pages.add(page)
        if self.matched_ids:
            start_idx = page * self.CHUNK_SIZE
            end_idx = min(len(self.matched_ids), (page + 1) * self.CHUNK_SIZE)
            page_ids = self.matched_ids[start_idx:end_idx]
            self.client.send_request(
                "get_game_summaries",
                {"game_ids": page_ids},
                callback=lambda resp, p=page: self._on_summaries_received(resp, p),
            )
        else:
            params = dict(self.filters)
            params["page"] = page
            params["page_size"] = self.CHUNK_SIZE
            self.client.send_request("query_games", params)

    def _on_summaries_received(self, resp: dict, page: int):
        if resp.get("status") != "ok":
            return
        games = resp.get("data", {}).get("game_summaries", [])
        if page in self.in_flight_pages:
            self.in_flight_pages.remove(page)

        self.cached_chunks[page] = games
        self.cached_chunks.move_to_end(page)

        while len(self.cached_chunks) > self.MAX_CACHED_CHUNKS:
            self.cached_chunks.popitem(last=False)

        start_row = page * self.CHUNK_SIZE
        end_row = min(self.total_count - 1, start_row + len(games) - 1)
        if start_row <= end_row:
            top_left = self.index(start_row, 0)
            bottom_right = self.index(end_row, len(self.HEADERS) - 1)
            self.dataChanged.emit(
                top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole]
            )

        loaded_count = sum(len(c) for c in self.cached_chunks.values())
        self.stats_updated.emit(self.total_count, loaded_count)

    def set_matched_ids(self, ids: List[int]):
        """Filter table to a specific set of 0-based game IDs (e.g. from CQL search)."""
        self.beginResetModel()
        self.matched_ids = list(ids)
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.total_count = len(ids)
        self.endResetModel()

        if self.client.is_running() and self.total_count > 0:
            self._request_chunk(0)

    def set_filter_text(self, text: str):
        self.matched_ids = []
        filters = dict(self.filters)
        text = text.strip()
        if text:
            filters["player"] = text
        else:
            filters.pop("player", None)
        self.set_filters(filters)

    def sort(self, col: int, order: Qt.SortOrder):
        if col not in self.COLUMN_SORT_FIELDS:
            return
        self.sort_col = col
        self.sort_asc = order == Qt.AscendingOrder
        self.filters["sort_by"] = self.COLUMN_SORT_FIELDS[col]
        self.filters["sort_asc"] = self.sort_asc
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.HEADERS) - 1)
        self.invalidate_cache_and_reload()

    def set_filters(self, filters: dict):
        self.beginResetModel()
        self.matched_ids = []
        self.filters = dict(filters)
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.total_count = 0
        self.endResetModel()

        if self.client.is_running():
            self._request_chunk(0)

    def invalidate_cache_and_reload(self):
        self.beginResetModel()
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.endResetModel()

        if self.client.is_running():
            self._request_chunk(0)

    def clear(self):
        self.beginResetModel()
        self.matched_ids = []
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.total_count = 0
        self.pgn_path = None
        self.endResetModel()
        self.stats_updated.emit(0, 0)

    def on_backend_response(self, data: dict):
        if data.get("status") != "ok":
            return
        resp_data = data.get("data", {})
        if "games" not in resp_data:
            return

        page = resp_data.get("page", 0)
        total = resp_data.get("total", 0)
        games = resp_data.get("games", [])

        if page in self.in_flight_pages:
            self.in_flight_pages.remove(page)

        self.cached_chunks[page] = games
        self.cached_chunks.move_to_end(page)

        while len(self.cached_chunks) > self.MAX_CACHED_CHUNKS:
            self.cached_chunks.popitem(last=False)

        if total != self.total_count:
            self.beginResetModel()
            self.total_count = total
            self.endResetModel()
        else:
            start_row = page * self.CHUNK_SIZE
            end_row = min(self.total_count - 1, start_row + len(games) - 1)
            if start_row <= end_row:
                top_left = self.index(start_row, 0)
                bottom_right = self.index(end_row, len(self.HEADERS) - 1)
                self.dataChanged.emit(
                    top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole]
                )

        loaded_count = sum(len(c) for c in self.cached_chunks.values())
        self.stats_updated.emit(self.total_count, loaded_count)


class GameListTableWidget(QtWidgets.QWidget):
    """
    Virtual game list table backed by the high-performance Rust scid-mgr process.
    Supports asynchronous virtual scrolling, header persistence, and double-click game inspection.
    """

    gameSelected = QtCore.pyqtSignal(dict)
    loadFinished = QtCore.pyqtSignal(int)

    def __init__(self, client: Optional[BackendClient] = None, parent=None):
        super().__init__(parent)
        self.client = client or BackendClient(self)

        self.filter_edit = QtWidgets.QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter games instantly by player name...")

        # Chip Bar for active filters
        self.chip_bar = QtWidgets.QFrame(self)
        self.chip_bar.setObjectName("filterChipBar")
        self.chip_bar.setStyleSheet("""
            QFrame#filterChipBar {
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 4px 8px;
                margin-top: 2px;
                margin-bottom: 2px;
            }
            QLabel#chipLabel {
                color: #166534;
                font-weight: bold;
                font-size: 11px;
            }
            QLabel#chipTags {
                color: #15803d;
                font-size: 11px;
            }
            QPushButton#chipClearBtn {
                background-color: #dcfce7;
                color: #14532d;
                border: 1px solid #bbf7d0;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#chipClearBtn:hover {
                background-color: #fee2e2;
                color: #991b1b;
                border-color: #fca5a5;
            }
        """)
        chip_layout = QtWidgets.QHBoxLayout(self.chip_bar)
        chip_layout.setContentsMargins(6, 2, 6, 2)
        chip_layout.setSpacing(8)

        self.chip_title = QtWidgets.QLabel("🏷️ Filters Applied:", self.chip_bar)
        self.chip_title.setObjectName("chipLabel")
        chip_layout.addWidget(self.chip_title)

        self.chip_tags = QtWidgets.QLabel("", self.chip_bar)
        self.chip_tags.setObjectName("chipTags")
        chip_layout.addWidget(self.chip_tags, 1)

        self.chip_clear_btn = QtWidgets.QPushButton("✕ Reset Filters", self.chip_bar)
        self.chip_clear_btn.setObjectName("chipClearBtn")
        self.chip_clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.chip_clear_btn.clicked.connect(self.clear_filters)
        chip_layout.addWidget(self.chip_clear_btn)

        self.chip_bar.hide()

        self.table = QtWidgets.QTableView(self)
        self.table.setFont(QtGui.QFont("Segoe UI", 10))
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)

        self.info_label = QtWidgets.QLabel(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.chip_bar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.info_label)

        self.model = GameListTableModel(self.client, self)
        self.model.modelReset.connect(self._update_chip_bar)
        self.table.setModel(self.model)

        # 150ms debounce timer for virtual scrolling chunk requests
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.setInterval(150)
        self.scroll_timer.timeout.connect(self._on_scroll_settled)

        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)

        # Reordering and layout persistence setup
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self.save_header_state)
        header.sectionResized.connect(self.save_header_state)
        header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)

        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        self.client.response_received.connect(self._on_backend_response)

    def set_client(self, client: BackendClient):
        self.client = client
        self.model.client = client
        self.client.response_received.connect(self.model.on_backend_response)
        self.client.response_received.connect(self._on_backend_response)

    def load_db(self, db_path: str, pgn_path: Optional[str] = None):
        """Opens database or PGN archive in scid-mgr backend."""
        target_path = pgn_path if (pgn_path and os.path.exists(pgn_path)) else db_path
        self.model.pgn_path = target_path

        if not self.client.is_running():
            self.client.start(db_path=target_path)

        self.client.send_request("open", {"path": target_path})
        self.restore_header_state()

    def clear(self):
        """Clears current model data and table selection."""
        self.model.clear()
        self.set_info_text("")

    def set_info_text(self, text: str):
        self.info_label.setText(str(text))

    def _on_scroll_changed(self, _val):
        self.scroll_timer.start()

    def _on_scroll_settled(self):
        top_row = self.table.rowAt(0)
        bottom_row = self.table.rowAt(self.table.viewport().height())

        if top_row == -1:
            top_row = 0
        if bottom_row == -1:
            bottom_row = min(self.model.total_count, top_row + 50)

        self.model.request_chunks_for_range(top_row, bottom_row)

    def apply_cql_matches(self, match_indices: list):
        """Filters the table to display games matching CQL search results directly."""
        zero_based = [idx - 1 for idx in match_indices if idx > 0]
        self.model.set_matched_ids(zero_based)
        self.set_info_text(f"{len(zero_based):,} games matching CQL query")
        self._update_chip_bar(cql_count=len(zero_based))

    def clear_filters(self):
        """Clears all active filters and requests full database headers without re-indexing."""
        self.filter_edit.blockSignals(True)
        self.filter_edit.clear()
        self.filter_edit.blockSignals(False)
        self.model.set_filters({})
        self._update_chip_bar()

    def _update_chip_bar(self, cql_count: Optional[int] = None):
        active_filters = {
            k: v
            for k, v in self.model.filters.items()
            if k not in ("sort_by", "sort_asc", "page", "page_size") and v
        }
        has_cql = len(self.model.matched_ids) > 0 or cql_count is not None
        if not active_filters and not has_cql:
            self.chip_bar.hide()
            return

        tag_strs = []
        if has_cql:
            count = cql_count if cql_count is not None else len(self.model.matched_ids)
            tag_strs.append(f"<b>⚡ CQL Query Matches</b>: {count:,} games")
        for k, v in active_filters.items():
            tag_strs.append(f"<b>{k.title()}</b>: {v}")

        self.chip_tags.setText(" &nbsp;|&nbsp; ".join(tag_strs))
        self.chip_bar.show()

    def _on_filter_text_changed(self, text: str):
        self.model.set_filter_text(text)
        self._update_chip_bar()

    def _on_header_clicked(self, logical_index: int):
        order = self.table.horizontalHeader().sortIndicatorOrder()
        self.model.sort(logical_index, order)

    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid():
            return

        row_idx = proxy_index.row()
        game_item = self.model.get_game_at(row_idx)
        if not game_item:
            return

        game_id = game_item.get("id", row_idx)

        # Request full PGN text asynchronously from scid-mgr
        def _on_pgn_received(resp: dict):
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                payload = {
                    "ID": str(game_item.get("id", row_idx)),
                    "White": game_item.get("white", ""),
                    "EloW": str(game_item.get("white_elo", "")),
                    "Black": game_item.get("black", ""),
                    "EloB": str(game_item.get("black_elo", "")),
                    "Result": game_item.get("result", ""),
                    "ECO": game_item.get("eco", ""),
                    "Date": game_item.get("date", ""),
                    "Event": game_item.get("event", ""),
                    "Site": game_item.get("site", ""),
                    "Round": game_item.get("round", ""),
                    "PGN": pgn_text,
                    "_pgn_path": self.model.pgn_path,
                }
                self.gameSelected.emit(payload)

        self.client.send_request(
            "get_pgn", {"index": game_id}, callback=_on_pgn_received
        )

    def _on_backend_response(self, data: dict):
        if data.get("status") != "ok":
            return
        resp_data = data.get("data", {})
        if "stats" in resp_data:
            total = resp_data["stats"].get("total_games", 0)
            self.set_info_text(f"{total:,} games in database")
            self.loadFinished.emit(total)
            # Fetch first chunk of games
            self.model.invalidate_cache_and_reload()
        elif "total" in resp_data and "games" in resp_data:
            total = resp_data.get("total", 0)
            self.set_info_text(f"{total:,} games matching")
            self.loadFinished.emit(total)

    def save_header_state(self):
        settings = QSettings("TestChessApp", "Config")
        settings.setValue(
            "table_header_state", self.table.horizontalHeader().saveState()
        )

    def restore_header_state(self):
        settings = QSettings("TestChessApp", "Config")
        state = settings.value("table_header_state")
        if state is not None:
            self.table.horizontalHeader().restoreState(state)
        else:
            self._apply_default_widths()

    def _apply_default_widths(self):
        default_widths = {
            "ID": 60,
            "White": 160,
            "EloW": 75,
            "Black": 160,
            "EloB": 75,
            "Result": 75,
            "ECO": 65,
            "Date": 95,
            "Event": 180,
            "Site": 150,
            "Round": 60,
            "Status": 75,
        }
        for i, h in enumerate(GameListTableModel.HEADERS):
            width = default_widths.get(h, 100)
            self.table.setColumnWidth(i, width)

    def _on_header_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        header = self.table.horizontalHeader()
        for idx in range(len(GameListTableModel.HEADERS)):
            name = GameListTableModel.HEADERS[idx]
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(idx))
            action.triggered.connect(
                lambda checked, col_idx=idx: self.toggle_column_visibility(
                    col_idx, checked
                )
            )

        menu.addSeparator()
        config_action = menu.addAction("Configure Columns...")
        config_action.triggered.connect(self.configure_columns)
        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx, visible):
        self.table.horizontalHeader().setSectionHidden(col_idx, not visible)
        self.save_header_state()

    def configure_columns(self):
        dlg = ColumnConfigDialog(
            self.table.horizontalHeader(), GameListTableModel.HEADERS, self
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            settings = dlg.get_column_settings()
            header = self.table.horizontalHeader()
            header.blockSignals(True)

            for visual_idx, s in enumerate(settings):
                logical_idx = s["logical_idx"]
                visible = s["visible"]
                header.setSectionHidden(logical_idx, not visible)
                curr_vis = header.visualIndex(logical_idx)
                if curr_vis != visual_idx:
                    header.moveSection(curr_vis, visual_idx)

            header.blockSignals(False)
            self.save_header_state()


class ColumnConfigDialog(QtWidgets.QDialog):
    def __init__(self, header_view, headers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Columns")
        self.resize(320, 400)
        self.header_view = header_view
        self.headers = headers

        layout = QtWidgets.QVBoxLayout(self)

        info_lbl = QtWidgets.QLabel(
            "Drag items or use buttons to reorder.\nCheck/uncheck to show/hide columns."
        )
        info_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(info_lbl)

        # List Widget
        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.up_btn = QtWidgets.QPushButton("Move Up")
        self.down_btn = QtWidgets.QPushButton("Move Down")
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        layout.addLayout(btn_layout)

        # Buttons box
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_columns()

        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)

    def load_columns(self):
        visual_map = {}
        for logical_idx in range(len(self.headers)):
            vis_idx = self.header_view.visualIndex(logical_idx)
            visual_map[vis_idx] = logical_idx

        for vis_idx in sorted(visual_map.keys()):
            logical_idx = visual_map[vis_idx]
            name = self.headers[logical_idx]
            is_hidden = self.header_view.isSectionHidden(logical_idx)

            item = QtWidgets.QListWidgetItem(name, self.list_widget)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemIsUserCheckable
                | QtCore.Qt.ItemIsSelectable
                | QtCore.Qt.ItemIsDragEnabled
            )
            item.setCheckState(QtCore.Qt.Unchecked if is_hidden else QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, logical_idx)

    def move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def get_column_settings(self):
        settings = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            logical_idx = item.data(QtCore.Qt.UserRole)
            visible = item.checkState() == QtCore.Qt.Checked
            settings.append({"logical_idx": logical_idx, "visible": visible})
        return settings
