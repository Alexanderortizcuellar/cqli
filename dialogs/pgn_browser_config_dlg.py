import qtawesome as qta
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QDialogButtonBox,
    QGroupBox,
)
from PyQt5.QtCore import QSettings


class PGNBrowserConfigDialog(QDialog):
    """
    Configuration dialog for QPainterPGNBrowser options:
    - Display mode: Blocks (ChessBase style) vs Columns (Move-by-move / Linear)
    - Show inline engine evaluation
    - Show color move classifications (blunders, mistakes, inaccuracies, brilliant)
    - Show comments & variations
    - Compact spacing
    """

    def __init__(self, parent=None, initial_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Configure PGN Notation Browser")
        self.resize(440, 360)
        self.settings = QSettings("TestChessApp", "PGNBrowser")

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # ── Display Layout ───────────────────────────────────────────────
        layout_group = QGroupBox(" Display Layout")
        layout_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout_form = QFormLayout(layout_group)
        layout_form.setSpacing(8)

        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItem("Blocks (ChessBase Style)", 1)
        self.display_mode_combo.addItem("Columns (Move-by-Move)", 0)
        layout_form.addRow("Move Layout:", self.display_mode_combo)

        self.compact_cb = QCheckBox("Compact move spacing")
        layout_form.addRow("", self.compact_cb)

        main_layout.addWidget(layout_group)

        # ── Annotations & Analysis ───────────────────────────────────────
        analysis_group = QGroupBox(" Annotations & Analysis")
        analysis_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        analysis_layout = QVBoxLayout(analysis_group)
        analysis_layout.setSpacing(8)

        self.eval_cb = QCheckBox("Show inline engine evaluations (e.g. +0.3, #2)")
        self.eval_cb.setIcon(qta.icon("fa5s.chart-line", color="#3b82f6"))

        self.classification_cb = QCheckBox(
            "Show color move classifications (Brilliant, Blunder, Mistake, etc.)"
        )
        self.classification_cb.setIcon(qta.icon("fa5s.palette", color="#10b981"))

        self.comments_cb = QCheckBox("Show text comments and annotations")
        self.comments_cb.setIcon(qta.icon("fa5s.comment-dots", color="#f59e0b"))

        self.variations_cb = QCheckBox("Show alternative variations")
        self.variations_cb.setIcon(qta.icon("fa5s.code-branch", color="#8b5cf6"))

        analysis_layout.addWidget(self.eval_cb)
        analysis_layout.addWidget(self.classification_cb)
        analysis_layout.addWidget(self.comments_cb)
        analysis_layout.addWidget(self.variations_cb)

        main_layout.addWidget(analysis_group)

        # ── Buttons ──────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setIcon(qta.icon("ei.check"))
        buttons.button(QDialogButtonBox.Cancel).setIcon(qta.icon("fa5s.times"))
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Load values
        if initial_settings:
            self.load_from_dict(initial_settings)
        else:
            self.load_from_settings()

    def load_from_settings(self):
        mode = int(self.settings.value("layout_mode", 1))
        idx = self.display_mode_combo.findData(mode)
        if idx >= 0:
            self.display_mode_combo.setCurrentIndex(idx)

        self.compact_cb.setChecked(self.settings.value("cb_compact", False, type=bool))
        self.eval_cb.setChecked(self.settings.value("show_eval", True, type=bool))
        self.classification_cb.setChecked(
            self.settings.value("show_classifications", True, type=bool)
        )
        self.comments_cb.setChecked(
            self.settings.value("show_comments", True, type=bool)
        )
        self.variations_cb.setChecked(
            self.settings.value("show_variations", True, type=bool)
        )

    def load_from_dict(self, cfg: dict):
        mode = cfg.get("layout_mode", 1)
        idx = self.display_mode_combo.findData(mode)
        if idx >= 0:
            self.display_mode_combo.setCurrentIndex(idx)

        self.compact_cb.setChecked(bool(cfg.get("cb_compact", False)))
        self.eval_cb.setChecked(bool(cfg.get("show_eval", True)))
        self.classification_cb.setChecked(bool(cfg.get("show_classifications", True)))
        self.comments_cb.setChecked(bool(cfg.get("show_comments", True)))
        self.variations_cb.setChecked(bool(cfg.get("show_variations", True)))

    def get_settings(self) -> dict:
        return {
            "layout_mode": self.display_mode_combo.currentData(),
            "cb_compact": self.compact_cb.isChecked(),
            "show_eval": self.eval_cb.isChecked(),
            "show_classifications": self.classification_cb.isChecked(),
            "show_comments": self.comments_cb.isChecked(),
            "show_variations": self.variations_cb.isChecked(),
        }

    def save_and_accept(self):
        cfg = self.get_settings()
        for k, v in cfg.items():
            self.settings.setValue(k, v)
        self.accept()
