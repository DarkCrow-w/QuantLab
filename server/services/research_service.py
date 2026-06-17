from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from server.models.backtest import BacktestRequest, BacktestResult

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "meta" / "research.sqlite3"


class ResearchStore:
    """SQLite-backed research artifact registry."""

    def __init__(self, db_path: Path | str = _DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    strategy TEXT NOT NULL,
                    symbols TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_return REAL NOT NULL,
                    annual_return REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    sharpe_ratio REAL,
                    win_rate REAL,
                    trade_count INTEGER NOT NULL,
                    final_equity REAL NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    note TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_backtest_runs_created
                    ON backtest_runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy
                    ON backtest_runs(strategy, created_at DESC);
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(backtest_runs)").fetchall()
            }
            migrations = {
                "updated_at": "ALTER TABLE backtest_runs ADD COLUMN updated_at TEXT",
                "tags_json": "ALTER TABLE backtest_runs ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'",
                "note": "ALTER TABLE backtest_runs ADD COLUMN note TEXT NOT NULL DEFAULT ''",
                "favorite": "ALTER TABLE backtest_runs ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    conn.execute(statement)

    def save_backtest(self, request: BacktestRequest, result: BacktestResult) -> dict:
        run_id = uuid.uuid4().hex
        created_at = datetime.now().isoformat(timespec="seconds")
        request_data = _model_dict(request)
        result_data = _model_dict(result)
        metrics = result.metrics
        row = {
            "id": run_id,
            "created_at": created_at,
            "updated_at": created_at,
            "strategy": request.strategy,
            "symbols": ",".join(request.symbols),
            "start_date": request.start_date,
            "end_date": request.end_date,
            "total_return": metrics.total_return,
            "annual_return": metrics.annual_return,
            "max_drawdown": metrics.max_drawdown,
            "sharpe_ratio": metrics.sharpe_ratio,
            "win_rate": metrics.win_rate,
            "trade_count": metrics.trade_count,
            "final_equity": metrics.final_equity,
            "tags_json": "[]",
            "note": "",
            "favorite": 0,
            "request_json": json.dumps(request_data, ensure_ascii=False),
            "metrics_json": json.dumps(_model_dict(metrics), ensure_ascii=False),
            "result_json": json.dumps(result_data, ensure_ascii=False),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backtest_runs(
                    id, created_at, updated_at, strategy, symbols, start_date, end_date,
                    total_return, annual_return, max_drawdown, sharpe_ratio,
                    win_rate, trade_count, final_equity, tags_json, note, favorite, request_json,
                    metrics_json, result_json
                ) VALUES (
                    :id, :created_at, :updated_at, :strategy, :symbols, :start_date, :end_date,
                    :total_return, :annual_return, :max_drawdown, :sharpe_ratio,
                    :win_rate, :trade_count, :final_equity, :tags_json, :note, :favorite, :request_json,
                    :metrics_json, :result_json
                )
                """,
                row,
            )
        return self.get_backtest(run_id) or {}

    def list_backtests(
        self,
        limit: int = 50,
        strategy: str | None = None,
        favorite: bool | None = None,
        tag: str | None = None,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        params: list[Any] = []
        conditions: list[str] = []
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if favorite is not None:
            conditions.append("favorite = ?")
            params.append(1 if favorite else 0)
        if tag:
            conditions.append("tags_json LIKE ?")
            encoded = json.dumps(str(tag).strip()[:32], ensure_ascii=False)
            params.append(f"%{encoded}%")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, created_at, updated_at, strategy, symbols, start_date, end_date,
                       total_return, annual_return, max_drawdown, sharpe_ratio,
                       win_rate, trade_count, final_equity, tags_json, note, favorite
                FROM backtest_runs
                {where}
                ORDER BY favorite DESC, created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [_summary(dict(row)) for row in rows]

    def get_backtest(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        return {
            **_summary(data),
            "request": json.loads(data["request_json"]),
            "metrics": json.loads(data["metrics_json"]),
            "result": json.loads(data["result_json"]),
        }

    def update_backtest_metadata(
        self,
        run_id: str,
        *,
        tags: list[str] | None = None,
        note: str | None = None,
        favorite: bool | None = None,
    ) -> dict | None:
        existing = self.get_backtest(run_id)
        if existing is None:
            return None
        next_tags = existing["tags"] if tags is None else _normalize_tags(tags)
        next_note = existing["note"] if note is None else str(note).strip()[:2000]
        next_favorite = existing["favorite"] if favorite is None else bool(favorite)
        updated_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE backtest_runs
                SET tags_json = ?, note = ?, favorite = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(next_tags, ensure_ascii=False),
                    next_note,
                    1 if next_favorite else 0,
                    updated_at,
                    run_id,
                ),
            )
        return self.get_backtest(run_id)

    def build_backtest_report(self, run_ids: list[str]) -> str | None:
        ids = [str(run_id).strip() for run_id in run_ids if str(run_id).strip()]
        if not ids:
            return None
        runs = []
        for run_id in ids[:12]:
            run = self.get_backtest(run_id)
            if run is None:
                return None
            runs.append(run)
        generated_at = datetime.now().isoformat(timespec="seconds")
        lines = [
            "# QuantLab Research Report",
            "",
            f"- Generated at: `{generated_at}`",
            f"- Experiments: `{len(runs)}`",
            "",
            "## Summary",
            "",
            "| ID | Strategy | Symbols | Period | Return | Annual | Drawdown | Sharpe | Trades | Tags |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for run in runs:
            lines.append(
                "| {id} | {strategy} | {symbols} | {period} | {ret} | {ann} | {dd} | {sharpe} | {trades} | {tags} |".format(
                    id=run["id"][:8],
                    strategy=run["strategy"],
                    symbols=", ".join(run["symbols"]),
                    period=f"{run['start_date']} ~ {run['end_date']}",
                    ret=_fmt_pct(run["total_return"]),
                    ann=_fmt_pct(run["annual_return"]),
                    dd=_fmt_pct(run["max_drawdown"]),
                    sharpe="-" if run["sharpe_ratio"] is None else f"{run['sharpe_ratio']:.4f}",
                    trades=run["trade_count"],
                    tags=", ".join(run["tags"]) or "-",
                )
            )

        best = max(runs, key=lambda item: item["total_return"])
        least_drawdown = max(runs, key=lambda item: item["max_drawdown"])
        lines.extend(
            [
                "",
                "## Highlights",
                "",
                f"- Best return: `{best['id'][:8]}` at `{_fmt_pct(best['total_return'])}`.",
                f"- Least drawdown: `{least_drawdown['id'][:8]}` at `{_fmt_pct(least_drawdown['max_drawdown'])}`.",
                "",
                "## Experiment Details",
                "",
            ]
        )
        for run in runs:
            lines.extend(
                [
                    f"### {run['id'][:8]} - {run['strategy']}",
                    "",
                    f"- Favorite: `{'yes' if run['favorite'] else 'no'}`",
                    f"- Tags: `{', '.join(run['tags']) or '-'}`",
                    f"- Note: {run['note'] or '-'}",
                    f"- Final equity: `{run['final_equity']:.2f}`",
                    f"- Win rate: `{_fmt_pct(run['win_rate'])}`",
                    f"- Equity points: `{len(run['result'].get('equity_curve', []))}`",
                    f"- Trades: `{len(run['result'].get('trades', []))}`",
                    "",
                    "Request:",
                    "",
                    "```json",
                    json.dumps(run["request"], ensure_ascii=False, indent=2),
                    "```",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def summary(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       MAX(created_at) AS latest_at,
                       AVG(total_return) AS avg_total_return,
                       MAX(total_return) AS best_total_return,
                       MIN(max_drawdown) AS worst_drawdown
                FROM backtest_runs
                """
            ).fetchone()
            best = conn.execute(
                """
                SELECT id, created_at, strategy, symbols, start_date, end_date,
                       total_return, annual_return, max_drawdown, sharpe_ratio,
                       win_rate, trade_count, final_equity, tags_json, note, favorite,
                       updated_at
                FROM backtest_runs
                ORDER BY total_return DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return {
            "total_backtests": int(row["total"] or 0),
            "latest_at": row["latest_at"],
            "avg_total_return": row["avg_total_return"],
            "best_total_return": row["best_total_return"],
            "worst_drawdown": row["worst_drawdown"],
            "best_run": _summary(dict(best)) if best is not None else None,
            "favorite_count": self._favorite_count(),
            "tags": self._tag_counts(),
        }

    def _favorite_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM backtest_runs WHERE favorite = 1").fetchone()
        return int(row["total"] or 0)

    def _tag_counts(self) -> list[dict]:
        counts: dict[str, int] = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT tags_json FROM backtest_runs").fetchall()
        for row in rows:
            for tag in _parse_tags(row["tags_json"]):
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]


def _summary(row: dict) -> dict:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at") or row["created_at"],
        "strategy": row["strategy"],
        "symbols": [symbol for symbol in str(row["symbols"]).split(",") if symbol],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "total_return": row["total_return"],
        "annual_return": row["annual_return"],
        "max_drawdown": row["max_drawdown"],
        "sharpe_ratio": row["sharpe_ratio"],
        "win_rate": row["win_rate"],
        "trade_count": row["trade_count"],
        "final_equity": row["final_equity"],
        "tags": _parse_tags(row.get("tags_json")),
        "note": row.get("note") or "",
        "favorite": bool(row.get("favorite") or 0),
    }


def _model_dict(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return _normalize_tags([str(item) for item in raw])


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        item = str(tag).strip()
        if not item or item in normalized:
            continue
        normalized.append(item[:32])
        if len(normalized) >= 12:
            break
    return normalized


def _fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


_STORE: ResearchStore | None = None


def get_research_store() -> ResearchStore:
    global _STORE
    if _STORE is None:
        _STORE = ResearchStore()
    return _STORE
