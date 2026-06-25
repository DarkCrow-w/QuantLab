from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from quant.config import get_settings
from quant.data import INDICATORS, get_store
from quant.data.symbol_filter import filter_a_share_rows
from quant.data.updater import list_cached_symbols
from server.agent.model import get_agent_runtime_status
from server.services.backtest_service import get_strategy_list
from server.services.data_job_service import get_data_job_manager
from server.services.research_service import get_research_store
from server.services.trading_service import get_trading_status

SystemLevel = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class SystemCheck:
    key: str
    label: str
    level: SystemLevel
    message: str
    detail: dict
    required: bool = True

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "level": self.level,
            "message": self.message,
            "detail": self.detail,
            "required": self.required,
        }


def get_system_status() -> dict:
    """Return a lightweight readiness snapshot for the web console.

    The checks are intentionally read-only. They do not probe remote data
    providers, connect to Futu OpenD, trigger downloads, or instantiate an LLM.
    """
    settings = get_settings()
    store = get_store()

    checks = [
        _api_check(),
        _config_check(settings),
        _data_cache_check(),
        _universe_check(store),
        _strategy_check(),
        _indicator_check(),
        _research_check(),
        _agent_check(),
        _live_trading_check(settings),
        _deployment_check(),
        _risk_check(),
    ]
    required_checks = [check for check in checks if check.required]
    required_ok = sum(check.level == "ok" for check in required_checks)
    score = round(required_ok / len(required_checks) * 100) if required_checks else 100
    overall: SystemLevel = (
        "error"
        if any(check.required and check.level == "error" for check in checks)
        else "warning"
        if any(check.required and check.level == "warning" for check in checks)
        else "ok"
    )

    latest_job = get_data_job_manager().latest()
    return {
        "status": overall,
        "score": score,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "required_ok": required_ok,
            "required_total": len(required_checks),
            "warnings": sum(check.level == "warning" for check in checks),
            "errors": sum(check.level == "error" for check in checks),
        },
        "checks": [check.to_dict() for check in checks],
        "latest_data_job": latest_job,
    }


def _api_check() -> SystemCheck:
    return SystemCheck(
        key="api",
        label="API 服务",
        level="ok",
        message="FastAPI 服务已就绪",
        detail={"service": "QuantLab API"},
    )


def _config_check(settings) -> SystemCheck:
    exists = settings.config_file.exists()
    return SystemCheck(
        key="config",
        label="统一配置",
        level="ok" if exists else "warning",
        message=(
            "已加载 config/quant.env"
            if exists
            else "未找到 config/quant.env，将使用进程环境变量和默认值"
        ),
        detail={
            "path": str(settings.config_file),
            "exists": exists,
            "backend_port": settings.app.backend_port,
            "frontend_port": settings.app.frontend_port,
            "cors_origins": list(settings.app.cors_origins),
        },
    )


def _data_cache_check() -> SystemCheck:
    cached = list_cached_symbols()
    latest_dates = sorted(
        [str(row.get("end")) for row in cached if row.get("end")],
    )
    count = len(cached)
    bars = sum(int(row.get("bars") or 0) for row in cached)
    level: SystemLevel = "ok" if count > 0 else "warning"
    return SystemCheck(
        key="data_cache",
        label="行情缓存",
        level=level,
        message=(
            f"本地已缓存 {count} 只标的"
            if count
            else "暂无本地行情缓存，回测和选股需要先下载或导入数据"
        ),
        detail={
            "cached_symbols": count,
            "bars": bars,
            "latest_date": latest_dates[-1] if latest_dates else None,
        },
    )


def _universe_check(store) -> SystemCheck:
    universe = store.get_universe()
    rows = [] if universe.empty else filter_a_share_rows(universe.to_dict(orient="records"))
    count = len(rows)
    markets = []
    if rows:
        markets = sorted({str(row.get("market")) for row in rows if row.get("market")})
    return SystemCheck(
        key="universe",
        label="股票池",
        level="ok" if count > 0 else "warning",
        message=(
            f"本地股票池包含 {count} 只标的"
            if count
            else "暂无本地股票池，数据平台可刷新 A 股股票列表"
        ),
        detail={"symbols": count, "markets": markets},
    )


def _strategy_check() -> SystemCheck:
    strategies = get_strategy_list()
    return SystemCheck(
        key="strategies",
        label="策略库",
        level="ok" if strategies else "error",
        message=f"已注册 {len(strategies)} 个策略" if strategies else "未注册任何策略",
        detail={
            "count": len(strategies),
            "names": [strategy.name for strategy in strategies],
        },
    )


def _indicator_check() -> SystemCheck:
    return SystemCheck(
        key="indicators",
        label="技术指标",
        level="ok" if INDICATORS else "error",
        message=f"已注册 {len(INDICATORS)} 个指标" if INDICATORS else "未注册任何指标",
        detail={"count": len(INDICATORS), "names": sorted(INDICATORS.keys())},
    )


def _research_check() -> SystemCheck:
    summary = get_research_store().summary()
    total = int(summary.get("total_backtests") or 0)
    return SystemCheck(
        key="research_assets",
        label="研究资产",
        level="ok" if total > 0 else "warning",
        message=(
            f"已沉淀 {total} 条回测实验记录"
            if total
            else "暂无研究实验记录，运行一次回测后会自动保存"
        ),
        detail=summary,
        required=False,
    )


def _agent_check() -> SystemCheck:
    status = get_agent_runtime_status()
    configured = bool(status.get("configured"))
    return SystemCheck(
        key="agent",
        label="AI 研究员",
        level="ok" if configured else "warning",
        message=(
            f"{status['provider']} / {status['model']} 已配置"
            if configured
            else str(status.get("reason") or "AI 模型未配置")
        ),
        detail=status,
        required=False,
    )


def _live_trading_check(settings) -> SystemCheck:
    status = get_trading_status()
    broker = status.get("broker", {})
    return SystemCheck(
        key="live_trading",
        label="实盘通道",
        level="warning" if status.get("ready") else "error",
        message=(
            "实盘配置已通过静态检查，启动前仍需人工确认账户与交易环境"
            if status.get("ready")
            else "实盘配置未通过静态检查，请先修复交易运行页中的 warning"
        ),
        detail={
            "broker": broker.get("type", "futu"),
            "host": broker.get("host", settings.futu.host),
            "port": broker.get("port", settings.futu.port),
            "entrypoint": status.get("entrypoint", "run_live.py"),
            "requires_manual_confirmation": True,
        },
        required=False,
    )


def _risk_check() -> SystemCheck:
    return SystemCheck(
        key="risk",
        label="风控内核",
        level="ok",
        message="基础仓位比例、最大回撤和交易成本控制已接入回测与实盘引擎",
        detail={
            "manager": "BasicRiskManager",
            "controls": ["max_position_pct", "max_drawdown", "commission_rate"],
        },
    )


def _deployment_check() -> SystemCheck:
    root = Path(__file__).resolve().parents[2]
    expected_files = [
        "Dockerfile",
        "docker-compose.yml",
        "web/Dockerfile",
        "web/nginx.conf",
        "config/quant.prod.env.example",
        "scripts/verify_deployment_config.py",
        "docs/DEPLOYMENT.md",
    ]
    missing = [path for path in expected_files if not (root / path).exists()]
    return SystemCheck(
        key="deployment",
        label="生产部署",
        level="ok" if not missing else "warning",
        message=(
            "Docker、Nginx、Compose 与部署验收脚本已就绪"
            if not missing
            else f"缺少 {len(missing)} 个部署文件，请先补齐部署配置"
        ),
        detail={
            "files": expected_files,
            "missing": missing,
            "verify_command": "python scripts/verify_deployment_config.py",
        },
        required=False,
    )
