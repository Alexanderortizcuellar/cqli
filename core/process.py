import re
from PyQt5.QtCore import pyqtSignal, QProcess, QThread


class CounterProcess(QThread):
    countFinished = pyqtSignal(int)

    def __init__(self, parent=None, filename: str = ""):
        super().__init__(parent)
        self.filename = filename

    def run(self):
        count = 0
        try:
            with open(self.filename, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().startswith("[Event "):
                        count += 1
        except Exception as e:
            print("Error counting games:", e)
        self.countFinished.emit(count)


class CQLProcess(QProcess):
    messageReceived = pyqtSignal(str)
    errorReceived = pyqtSignal(str)
    progressUpdated = pyqtSignal(int)
    statsReceived = pyqtSignal(dict)
    gamesReceived = pyqtSignal(str)
    finishedExecution = pyqtSignal(int, int, str)
    finishedSuccessfully = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProgram("cqli")
        self.readyReadStandardOutput.connect(self.read_stdout)
        self.readyReadStandardError.connect(self.read_stderr)
        self.finished.connect(self.on_finished)
        self.output_file = "temp_out.pgn"
        self.cql_file = "temp.cql"
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        self.matches_found = []
        self.games_processed = 0
        self.game_count = 0
        self.increment = 50

    def search(
        self,
        cqlquery: str,
        pgnfile: str,
        game_count: int = 0,
        elide_comments: bool = False,
        silent_mode: bool = False,
    ):
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        self.matches_found = []
        self.games_processed = 0
        self.game_count = game_count

        # Save query to temporary cql file
        with open(self.cql_file, "w", encoding="utf-8") as f:
            f.write(cqlquery)

        # Determine line increment to get smooth updates without spamming the UI
        # We aim for ~100 updates during execution
        self.increment = max(1, game_count // 100) if game_count > 0 else 50

        # Build arguments for cqli
        args = [
            "-i",
            pgnfile,
            "-o",
            self.output_file,
            "--showmatches",
            "--lineincrement",
            str(self.increment),
            "--nosort",
        ]

        if elide_comments:
            args.append("--elidecomments")
        if silent_mode:
            args.append("--silent")

        args.append(self.cql_file)

        self.setArguments(args)
        self.start()

    def read_stdout(self):
        data = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.stdout_buffer += data
        self.messageReceived.emit(data)
        self.parse_progress(data)

    def read_stderr(self):
        data = self.readAllStandardError().data().decode("utf-8", errors="replace")
        self.stderr_buffer += data

        # Remove progress tags [number] and <number> from stderr data for log cleanliness
        clean_data = re.sub(r"\[\d+\]|<\d+>", "", data)
        if clean_data.strip():
            self.errorReceived.emit(clean_data)

        self.parse_progress(data)

    def parse_progress(self, data: str):
        # Parse progress [number] and matches <number>
        # e.g. [4] or <4>
        for match in re.finditer(r"\[\d+\]", data):
            if self.game_count > 0:
                self.games_processed = min(
                    self.games_processed + self.increment, self.game_count
                )
            else:
                self.games_processed += self.increment
            self.progressUpdated.emit(self.games_processed)

        for match in re.finditer(r"<(\d+)>", data):
            game_num = int(match.group(1))
            self.matches_found.append(game_num)

    def on_finished(self, exit_code, exit_status):
        if exit_code == 0:
            # Emit stats parsed from summary output (support both singular "match" and plural "matches")
            summary_match = re.search(
                r"(\d+)\s+(?:CQL\s+)?match(?:es)?.*written",
                self.stdout_buffer,
                re.IGNORECASE,
            ) or re.search(
                r"(\d+)\s+CQL\s+match(?:es)?", self.stdout_buffer, re.IGNORECASE
            )
            total_games_match = re.search(
                r"Analyzed (\d+) games", self.stdout_buffer, re.IGNORECASE
            )

            stats = {}
            if summary_match:
                stats["numbermatches"] = int(summary_match.group(1))
            elif self.matches_found:
                stats["numbermatches"] = len(self.matches_found)
            else:
                # Count matches from output file if it exists and has content
                import os

                if (
                    os.path.exists(self.output_file)
                    and os.path.getsize(self.output_file) > 0
                ):
                    try:
                        count = 0
                        with open(
                            self.output_file, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            for line in f:
                                if line.startswith("[Event "):
                                    count += 1
                        stats["numbermatches"] = count
                    except Exception:
                        stats["numbermatches"] = 0
                else:
                    stats["numbermatches"] = 0

            if total_games_match:
                stats["totalgames"] = int(total_games_match.group(1))
            self.statsReceived.emit(stats)

            self.finishedSuccessfully.emit()

        self.finishedExecution.emit(exit_code, exit_status, self.stdout_buffer)
