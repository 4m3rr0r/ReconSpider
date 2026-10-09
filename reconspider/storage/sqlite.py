import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4


class SQLiteStore:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.run_id = uuid4().hex
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, started TEXT);
            CREATE TABLE IF NOT EXISTS records(run_id TEXT, sequence INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT);
            CREATE INDEX IF NOT EXISTS records_run ON records(run_id);
        """)
        self.connection.execute(
            "INSERT INTO runs VALUES (?, ?)", (self.run_id, datetime.now(timezone.utc).isoformat())
        )
        self.count = 0

    def write(self, item):
        self.connection.execute(
            "INSERT INTO records(run_id,data) VALUES (?,?)",
            (self.run_id, json.dumps(item, default=str)),
        )
        self.count += 1
        if self.count % 100 == 0:
            self.connection.commit()

    def close(self):
        self.connection.commit()
        self.connection.close()

    @staticmethod
    def read(path, run_id=None):
        connection = sqlite3.connect(path)
        try:
            if run_id is None:
                row = connection.execute(
                    "SELECT id FROM runs ORDER BY started DESC LIMIT 1"
                ).fetchone()
                if not row:
                    return
                run_id = row[0]
            for row in connection.execute(
                "SELECT data FROM records WHERE run_id=? ORDER BY sequence", (run_id,)
            ):
                yield json.loads(row[0])
        finally:
            connection.close()
