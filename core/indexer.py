import os
from PyQt5.QtCore import pyqtSignal, QProcess


class PGNIndexerProcess(QProcess):
    finishedSuccessfully = pyqtSignal(str)  # Emits the SQLite DB path
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
        # The database path will be the pgn path + ".db"
        self.db_path = pgn_path + ".db"

        # Check path of executable relative to application root
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe_path = os.path.join(
            app_dir, "pgn_indexer", "target", "release", "pgn_indexer.exe"
        )

        # Fallback to dev/debug if release is not there, though we expect release
        if not os.path.exists(exe_path):
            exe_path = os.path.join(
                app_dir, "pgn_indexer", "target", "debug", "pgn_indexer.exe"
            )

        if not os.path.exists(exe_path):
            # Try plain executable on system path
            exe_path = "pgn_indexer.exe"

        self.setProgram(exe_path)
        self.setArguments([pgn_path, self.db_path])
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
                f"Indexer failed with code {exit_code}:\n{self.output_buffer} and exit status {exit_status}"
            )
