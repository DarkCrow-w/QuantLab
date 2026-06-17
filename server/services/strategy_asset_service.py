from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from server.models.market import StrategyAsset, StrategyAssetDraft
from server.services.backtest_service import STRATEGY_REGISTRY

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "meta" / "strategies.sqlite3"


class StrategyAssetStore:
    def __init__(self, path: Path | str = _DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_assets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    base_strategy TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def list(self) -> list[StrategyAsset]:
        self._seed_defaults()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM strategy_assets ORDER BY updated_at DESC").fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, asset_id: str) -> StrategyAsset | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM strategy_assets WHERE id = ?", (asset_id,)).fetchone()
        return self._from_row(row) if row else None

    def save(self, draft: StrategyAssetDraft, asset_id: str | None = None) -> StrategyAsset:
        if draft.base_strategy not in STRATEGY_REGISTRY:
            raise ValueError(f"unknown base_strategy: {draft.base_strategy}")
        now = datetime.now().isoformat(timespec="seconds")
        asset_id = asset_id or uuid.uuid4().hex
        existing = self.get(asset_id)
        created_at = existing.created_at if existing else now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO strategy_assets(
                    id,name,description,base_strategy,params_json,tags_json,enabled,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    base_strategy=excluded.base_strategy,
                    params_json=excluded.params_json,
                    tags_json=excluded.tags_json,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    asset_id,
                    draft.name.strip(),
                    draft.description.strip(),
                    draft.base_strategy,
                    json.dumps(draft.params, ensure_ascii=False),
                    json.dumps(draft.tags, ensure_ascii=False),
                    int(draft.enabled),
                    created_at,
                    now,
                ),
            )
        return self.get(asset_id)  # type: ignore[return-value]

    def delete(self, asset_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM strategy_assets WHERE id = ?", (asset_id,))
        return cursor.rowcount > 0

    def _seed_defaults(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM strategy_assets").fetchone()[0]
        if count:
            return
        for name, info in STRATEGY_REGISTRY.items():
            params = {param.name: param.default for param in info["params_schema"]}
            self.save(
                StrategyAssetDraft(
                    name=str(info["display_name"]),
                    description="系统内置策略模板，可复制后调整参数。",
                    base_strategy=name,
                    params=params,
                    tags=["builtin"],
                    enabled=True,
                ),
                asset_id=f"builtin_{name}",
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> StrategyAsset:
        return StrategyAsset(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            base_strategy=row["base_strategy"],
            params=json.loads(row["params_json"] or "{}"),
            tags=json.loads(row["tags_json"] or "[]"),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


_STORE: StrategyAssetStore | None = None


def get_strategy_asset_store() -> StrategyAssetStore:
    global _STORE
    if _STORE is None:
        _STORE = StrategyAssetStore()
    return _STORE
