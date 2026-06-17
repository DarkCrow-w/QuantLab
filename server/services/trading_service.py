from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from quant.config import PROJECT_ROOT, get_settings
from server.services.backtest_service import STRATEGY_REGISTRY

DEFAULT_LIVE_CONFIG = PROJECT_ROOT / "configs" / "live_ma_cross.yaml"


def get_trading_status(config_path: Path | str = DEFAULT_LIVE_CONFIG) -> dict:
    """Return a read-only trading operations snapshot.

    This function deliberately does not connect to Futu OpenD or submit any
    order. It is intended for UI readiness checks and deployment diagnostics.
    """
    path = Path(config_path)
    cfg = _read_yaml(path)
    settings = get_settings()
    risk = cfg.get("risk", {})
    broker = cfg.get("broker", {})
    strategy = cfg.get("strategy", {})
    data = cfg.get("data", {})
    schedule = cfg.get("schedule", {})
    strategy_name = str(strategy.get("name", ""))

    checks = [
        _check(
            "config",
            "实盘配置",
            path.exists(),
            f"已读取 {path.name}" if path.exists() else f"未找到 {path}",
            {"path": str(path)},
        ),
        _check(
            "strategy",
            "策略注册",
            strategy_name in STRATEGY_REGISTRY,
            f"策略 {strategy_name} 已注册" if strategy_name in STRATEGY_REGISTRY else f"策略 {strategy_name or '-'} 未注册",
            {"strategy": strategy_name, "available": list(STRATEGY_REGISTRY)},
        ),
        _check(
            "symbols",
            "交易标的",
            bool(data.get("symbols")),
            f"已配置 {len(data.get('symbols') or [])} 只标的" if data.get("symbols") else "未配置交易标的",
            {"symbols": data.get("symbols") or []},
        ),
        _check(
            "risk",
            "风控参数",
            0 < float(risk.get("max_position_pct", 0)) <= 1 and 0 < float(risk.get("max_drawdown", 0)) <= 1,
            "仓位比例和最大回撤参数有效",
            {
                "max_position_pct": risk.get("max_position_pct"),
                "max_drawdown": risk.get("max_drawdown"),
            },
        ),
        _check(
            "broker",
            "交易通道",
            broker.get("type", "futu") == "futu",
            "Futu 通道已配置为实盘入口",
            {
                "type": broker.get("type", "futu"),
                "host": broker.get("host", settings.futu.host),
                "port": broker.get("port", settings.futu.port),
            },
        ),
    ]

    ready = all(check["level"] == "ok" for check in checks)
    return {
        "mode": "live",
        "ready": ready,
        "safety_mode": "manual_start",
        "config_path": str(path),
        "entrypoint": "python run_live.py configs/live_ma_cross.yaml",
        "strategy": {
            "name": strategy_name,
            "params": strategy.get("params", {}),
        },
        "data": {
            "source": data.get("source", "akshare"),
            "symbols": data.get("symbols") or [],
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "use_cache": bool(data.get("use_cache", False)),
        },
        "risk": {
            "manager": "BasicRiskManager",
            "max_position_pct": float(risk.get("max_position_pct", 0.3)),
            "max_drawdown": float(risk.get("max_drawdown", 0.2)),
        },
        "broker": {
            "type": broker.get("type", "futu"),
            "host": broker.get("host", settings.futu.host),
            "port": int(broker.get("port", settings.futu.port)),
            "connects_on_start": True,
        },
        "schedule": {
            "cron": "mon-fri",
            "hour": int(schedule.get("hour", 15)),
            "minute": int(schedule.get("minute", 5)),
        },
        "simulation": {
            "available": True,
            "broker": "SimulatedBroker",
            "entrypoint": "python run_backtest.py -c configs/backtest_ma_cross.yaml",
        },
        "checks": checks,
        "manual_confirmations": [
            "确认 Futu OpenD 已启动并连接到正确账户",
            "确认交易市场、账户权限、交易密码解锁状态和资金规模",
            "先用回测或仿真模式验证同一策略参数",
            "确认 max_position_pct、max_drawdown 和标的列表符合当日交易计划",
            "实盘运行前保留人工启动，不通过 Web UI 自动下单",
        ],
    }


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _check(key: str, label: str, ok: bool, message: str, detail: dict) -> dict:
    return {
        "key": key,
        "label": label,
        "level": "ok" if ok else "warning",
        "message": message,
        "detail": detail,
    }
