from __future__ import annotations

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "meta" / "strategies.sqlite3"


class StrategyVisibilityStore:
    def __init__(self, path: Path | str = _DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hidden_basic_strategies (
                    name TEXT PRIMARY KEY
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def list_hidden(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT name FROM hidden_basic_strategies").fetchall()
        return {str(row["name"]) for row in rows}

    def hide(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO hidden_basic_strategies(name) VALUES(?)",
                (name,),
            )

    def show(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM hidden_basic_strategies WHERE name = ?", (name,))


_STORE: StrategyVisibilityStore | None = None


def get_strategy_visibility_store() -> StrategyVisibilityStore:
    global _STORE
    if _STORE is None:
        _STORE = StrategyVisibilityStore()
    return _STORE
