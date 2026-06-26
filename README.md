# Chess CQLi Query Tool

A modern, fast, and feature-rich desktop application built with PyQt5 for querying, managing, and exploring PGN files using CQLi (Chess Query Language - version 6).

## Features

- **Advanced CQLi Querying:** Execute powerful CQLi queries against your PGN databases.
- **Smart Code Editor:** Integrated syntax-highlighting editor designed for CQL/CQLi scripting, with auto-completion and templates.
- **Game Explorer:** View matching games directly in the app. Includes a full chessboard view, move list, metadata panel, and variation trees.
- **Board Editor:** Set up custom positions easily using the interactive Board Editor with drag-and-drop piece palette, FEN generation, and castling/turn toggles. Includes a quick "Flip Board" option.
- **Engine Analysis:** Built-in support for UCI chess engines (e.g., Stockfish) directly within the game explorer. Includes live evaluation bars and engine configuration dialogs.
- **Customizable Layout:**
  - Fully adjustable column layouts for the Game List.
  - Light and Dark modes.
  - Flexible docking panels for Editor, Query Results, Log, and Analysis widgets.

## Architecture

- `main.py`: The main window orchestrating toolbars, menus, and layout.
- `core/`: Contains essential processing components like the `CQLProcess` executor, `PGNIndexerProcess`, and engine integrations.
- `widgets/`: Includes complex sub-views such as `CqlEditorWidget`, `GameExplorerWidget`, `GameListTableWidget`, `AnalysisWidget`, and custom UI models.
- `dialogs/`: Standalone dialogs like `BoardEditorDlg`, `QueryTemplatesDialog`, and engine configurations.

## Setup

1. **Requirements:**
   - Python 3.8+
   - PyQt5
   - `python-chess`
   - `qtawesome`
2. **CQL Executable:** Ensure the `cqli` engine is available in your PATH or configured correctly in the application.

## Run

Run the app by executing:

```bash
python main.py
```
