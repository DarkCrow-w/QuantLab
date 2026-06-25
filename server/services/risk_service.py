from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from server.models.risk import (
    RiskEvaluationCheck,
    RiskEvaluationRequest,
    RiskEvaluationResult,
    RiskRule,
    RiskRuleDraft,
)

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "meta" / "risk.sqlite3"


class RiskRuleStore:
    def __init__(self, path: Path | str = _DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    max_position_pct REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    max_single_order_pct REAL NOT NULL,
                    stop_loss_pct REAL NOT NULL,
                    take_profit_pct REAL NOT NULL,
                    max_symbols INTEGER NOT NULL,
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

    def list(self) -> list[RiskRule]:
        self._seed_default()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM risk_rules ORDER BY updated_at DESC").fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, rule_id: str) -> RiskRule | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM risk_rules WHERE id = ?", (rule_id,)).fetchone()
        return self._from_row(row) if row else None

    def save(self, draft: RiskRuleDraft, rule_id: str | None = None) -> RiskRule:
        now = datetime.now().isoformat(timespec="seconds")
        rule_id = rule_id or uuid.uuid4().hex
        existing = self.get(rule_id)
        created_at = existing.created_at if existing else now
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO risk_rules(
                    id,name,description,max_position_pct,max_drawdown,max_single_order_pct,
                    stop_loss_pct,take_profit_pct,max_symbols,enabled,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    max_position_pct=excluded.max_position_pct,
                    max_drawdown=excluded.max_drawdown,
                    max_single_order_pct=excluded.max_single_order_pct,
                    stop_loss_pct=excluded.stop_loss_pct,
                    take_profit_pct=excluded.take_profit_pct,
                    max_symbols=excluded.max_symbols,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    rule_id,
                    draft.name.strip(),
                    draft.description.strip(),
                    draft.max_position_pct,
                    draft.max_drawdown,
                    draft.max_single_order_pct,
                    draft.stop_loss_pct,
                    draft.take_profit_pct,
                    draft.max_symbols,
                    int(draft.enabled),
                    created_at,
                    now,
                ),
            )
        return self.get(rule_id)  # type: ignore[return-value]

    def delete(self, rule_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM risk_rules WHERE id = ?", (rule_id,))
        return cursor.rowcount > 0

    def _seed_default(self) -> None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM risk_rules WHERE id = ?", ("default_basic",)
            ).fetchone()
        if exists:
            return
        self.save(
            RiskRuleDraft(
                name="默认稳健风控",
                description="适合单策略研究与模拟交易的基础仓位、回撤和订单约束。",
            ),
            rule_id="default_basic",
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> RiskRule:
        return RiskRule(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            max_position_pct=float(row["max_position_pct"]),
            max_drawdown=float(row["max_drawdown"]),
            max_single_order_pct=float(row["max_single_order_pct"]),
            stop_loss_pct=float(row["stop_loss_pct"]),
            take_profit_pct=float(row["take_profit_pct"]),
            max_symbols=int(row["max_symbols"]),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def evaluate_risk(req: RiskEvaluationRequest, store: RiskRuleStore | None = None) -> RiskEvaluationResult:
    store = store or get_risk_rule_store()
    if req.draft is not None:
        rule = req.draft
    elif req.rule_id:
        saved = store.get(req.rule_id)
        if saved is None:
            raise ValueError("risk rule not found")
        rule = RiskRuleDraft(**saved.model_dump(exclude={"id", "created_at", "updated_at"}))
    else:
        saved = store.list()[0]
        rule = RiskRuleDraft(**saved.model_dump(exclude={"id", "created_at", "updated_at"}))

    checks = [
        RiskEvaluationCheck(
            key="position",
            label="持仓上限",
            passed=req.position_value <= req.equity * rule.max_position_pct,
            message=f"当前持仓 {req.position_value:.2f} / 上限 {req.equity * rule.max_position_pct:.2f}",
        ),
        RiskEvaluationCheck(
            key="order",
            label="单笔订单",
            passed=req.order_value <= req.equity * rule.max_single_order_pct,
            message=f"当前订单 {req.order_value:.2f} / 上限 {req.equity * rule.max_single_order_pct:.2f}",
        ),
        RiskEvaluationCheck(
            key="drawdown",
            label="最大回撤",
            passed=req.drawdown <= rule.max_drawdown,
            message=f"当前回撤 {req.drawdown:.2%} / 上限 {rule.max_drawdown:.2%}",
        ),
        RiskEvaluationCheck(
            key="symbols",
            label="持仓数量",
            passed=req.symbol_count <= rule.max_symbols,
            message=f"当前标的 {req.symbol_count} / 上限 {rule.max_symbols}",
        ),
    ]
    return RiskEvaluationResult(
        passed=all(check.passed for check in checks),
        rule=rule,
        checks=checks,
    )


_STORE: RiskRuleStore | None = None


def get_risk_rule_store() -> RiskRuleStore:
    global _STORE
    if _STORE is None:
        _STORE = RiskRuleStore()
    return _STORE
