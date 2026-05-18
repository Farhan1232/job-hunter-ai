import sqlite3
import os
from contextlib import contextmanager


class Storage:
    def __init__(self, path: str = "data/seen_jobs.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._init()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS seen (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    title TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def is_seen(self, job_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM seen WHERE id = ?", (job_id,)).fetchone()
            return row is not None

    def filter_unseen(self, jobs):
        with self._conn() as c:
            seen_ids = {r[0] for r in c.execute("SELECT id FROM seen").fetchall()}
        return [j for j in jobs if j.id not in seen_ids]

    def mark_seen(self, jobs):
        with self._conn() as c:
            c.executemany(
                "INSERT OR IGNORE INTO seen (id, source, title) VALUES (?,?,?)",
                [(j.id, j.source, j.title) for j in jobs],
            )

    def prune_old(self, days: int = 60):
        with self._conn() as c:
            c.execute(
                "DELETE FROM seen WHERE seen_at < datetime('now', ?)",
                (f"-{days} days",),
            )
