import os
from PyQt5.QtCore import pyqtSignal, QProcess


class ScidMgrProcess(QProcess):
    """
    QProcess wrapper around scid-mgr CLI for fast one-shot PGN / SCID index generation and metadata inspection.
    """

    finishedSuccessfully = pyqtSignal(str)  # Emits the index file or database path
    errorOccurred = pyqtSignal(str)
    progressMessage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProcessChannelMode(QProcess.MergedChannels)
        self.readyReadStandardOutput.connect(self.read_output)
        self.finished.connect(self.on_finished)
        self.db_path = None
        self.output_buffer = ""

    def index_pgn(self, pgn_path: str):
        self.output_buffer = ""
        self.db_path = pgn_path

        # Locate scid-mgr executable
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe_path = os.path.join(
            app_dir, "scid-mgr", "target", "release", "scid-mgr.exe"
        )

        if not os.path.exists(exe_path):
            exe_path = os.path.join(
                app_dir, "scid-mgr", "target", "debug", "scid-mgr.exe"
            )

        if not os.path.exists(exe_path):
            exe_path = "scid-mgr.exe"

        self.setProgram(exe_path)
        # Running 'info' automatically scans and generates the companion .pgn.idx index if missing or stale
        self.setArguments(["info", pgn_path])
        self.start()

    def read_output(self):
        data = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.output_buffer += data
        self.progressMessage.emit(data.strip())

    def on_finished(self, exit_code, exit_status):
        if exit_code == 0:
            self.finishedSuccessfully.emit(self.db_path)
        else:
            self.errorOccurred.emit(
                f"scid-mgr failed with code {exit_code}:\n{self.output_buffer} and exit status {exit_status}"
            )


# Backwards compatibility alias
PGNIndexerProcess = ScidMgrProcess
