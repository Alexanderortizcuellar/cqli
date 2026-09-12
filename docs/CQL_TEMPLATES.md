# CQL Query & Motif Templates Library

The Chess CQLi Query Tool includes an extensive built-in library of over **300 curated CQL queries** categorized by themes, tactical motifs, checkmating patterns, and endgame configurations.

---

## 📚 Categorized Collections

The query collection in [`data/queries.json`](file:///C:/Users/ASUS/programming/qt_programs/chess/cqli/data/queries.json) is organized into the following categories:

1. **FCE Table (Fundamental Chess Endings)**:
   - Categorized by piece distribution based on the Wikipedia / Müller & Lamprecht FCE frequency table (e.g., King & Pawn vs King, Rook Endings, Queen vs Rook, Minor Piece combinations).
2. **100 Endgames You Must Know (Jesus de la Villa)**:
   - Comprehensive rule-based queries for theoretical and practical endgame setups (Lucena position, Philidor defense, Vancura defense, Opposition, Triangulation, B+N mate, Wrong Rook Pawn, etc.).
3. **Lila Endgames**:
   - Advanced endgame motifs and positional balance queries.
4. **Checkmate Motifs**:
   - Classic checkmating patterns (Back Rank, Anastasia's Mate, Arabian Mate, Blackburne's Mate, Boden's Mate, Epaulette Mate, Smothered Mate, etc.).
5. **Tactical & Geometric Themes**:
   - Forks, Skewers, Discovered Attacks, Deflections, Decoys, Overloading, Windmill, Clearance, Interference, Desperado.
6. **Custom / User Templates**:
   - Custom CQL queries created, modified, or saved by the user via the Templates Explorer.

---

## 🔍 Using the Query Templates Explorer

Open the dialog via **Menu -> Tools -> Query Templates** or the list toolbar icon:

1. **Category Navigation**: Click any category branch in the left tree view to filter templates.
2. **Real-Time Search**: Type keywords into the search box (e.g. `lucena`, `philidor`, `queen`, `smothered`) to filter by name, description, or CQL keywords.
3. **Syntax Highlighted Preview**: Inspect the CQL code on the right panel with full syntax highlighting.
4. **Direct Insertion**: Double-click any query or click **Insert into Editor** to place the CQL code directly into the active CQL editor.
5. **Custom Management**: Create new templates or overwrite existing ones with one click.

---

## 🙏 Acknowledgements & Attribution

The core collection of endgame and motif CQL scripts was adapted from:
- **[elma16/reti](https://github.com/elma16/reti)**: Developed by **@elma16**. We express our sincere gratitude for making these structured CQL scripts open and accessible to the chess community.
