"""歷史紀錄（SQLite），存在 %APPDATA%\\ShuoShuo\\history.db。"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import data_dir


@dataclass
class Entry:
    id: int
    created: str
    kind: str        # dictation / meeting
    style: str
    engine: str
    raw: str
    final: str
    duration: float
    audio_path: str


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "history.db")
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'dictation',
                style TEXT, engine TEXT,
                raw TEXT, final TEXT,
                duration REAL DEFAULT 0,
                audio_path TEXT DEFAULT ''
            )"""
        )
        self._db.commit()

    def add(self, *, kind="dictation", style="", engine="", raw="", final="",
            duration=0.0, audio_path="") -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO entries (created, kind, style, engine, raw, final, duration, audio_path)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kind, style, engine,
                 raw, final, duration, audio_path),
            )
            self._db.commit()
            return cur.lastrowid

    def search(self, keyword: str = "", kind: str | None = None, limit: int = 300) -> list[Entry]:
        sql = "SELECT * FROM entries WHERE 1=1"
        args: list = []
        if keyword:
            sql += " AND (final LIKE ? OR raw LIKE ?)"
            args += [f"%{keyword}%", f"%{keyword}%"]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        return [Entry(*r) for r in rows]

    def recent_dictations(self, n: int = 10) -> list[Entry]:
        return self.search(kind="dictation", limit=n)

    def delete(self, entry_id: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
            self._db.commit()

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM entries")
            self._db.commit()
