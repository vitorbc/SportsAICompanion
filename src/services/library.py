"""Persist the active snapshot pointer, not raw documents or API credentials."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from src.core.models import Library, Match


class LibraryRegistry:
    def __init__(self, state_dir: Path):
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "libraries.sqlite3"
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS libraries ("
                "owner TEXT, match_id TEXT, payload TEXT NOT NULL, "
                "PRIMARY KEY (owner, match_id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS matches ("
                "owner TEXT, match_id TEXT, payload TEXT NOT NULL, "
                "PRIMARY KEY (owner, match_id))"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, owner: str, match_id: str) -> Library | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM libraries WHERE owner=? AND match_id=?",
                (owner, match_id),
            ).fetchone()
        return Library(**json.loads(row[0])) if row else None

    def activate(self, owner: str, match_id: str, library: Library) -> None:
        # One atomic transaction, only after every vector batch succeeds.
        with self._connect() as db:
            db.execute(
                "INSERT INTO libraries VALUES (?, ?, ?) "
                "ON CONFLICT(owner, match_id) DO UPDATE SET payload=excluded.payload",
                (owner, match_id, json.dumps(asdict(library))),
            )

    def add_match(self, owner: str, match: Match) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO matches VALUES (?, ?, ?)",
                       (owner, match.id, json.dumps(asdict(match))))

    def matches(self, owner: str) -> list[Match]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM matches WHERE owner=? ORDER BY rowid",
                              (owner,)).fetchall()
        result = []
        for row in rows:
            data = json.loads(row[0])
            data["participants"] = tuple(data["participants"])
            data["participant_assets"] = tuple(data.get("participant_assets", []))
            result.append(Match(**data))
        return result
