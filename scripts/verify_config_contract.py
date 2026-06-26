from __future__ import annotations

import json
import os
import re
from pathlib import Path

from quant.config import get_settings, reset_settings


ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV = ROOT / "config" / "quant.env.example"
PROD_ENV = ROOT / "config" / "quant.prod.env.example"

EXPECTED_KEYS = {
    "QUANT_BACKEND_HOST",
    "QUANT_BACKEND_PORT",
    "QUANT_FRONTEND_HOST",
    "QUANT_FRONTEND_PORT",
    "QUANT_CORS_ORIGINS",
    "QUANT_RELOAD",
    "QUANT_MEMORY_HIGH",
    "QUANT_MEMORY_MAX",
    "TUSHARE_TOKEN",
    "TUSHARE_RPM",
    "TUSHARE_WORKERS",
    "TUSHARE_RETRIES",
    "TUSHARE_FETCH_ADJ_FACTOR",
    "TDX_HOST",
    "TDX_PORT",
    "TDX_CONNECT_TIMEOUT",
    "TDX_MAX_HOST_ATTEMPTS",
    "TDX_HOST_COOLDOWN",
    "TDX_WORKERS",
    "TDX_REQUEST_RETRIES",
    "TDX_EMPTY_RESPONSE_THRESHOLD",
    "TDX_PROBE_TIMEOUT",
    "TDX_PROBE_WORKERS",
    "TDX_ACTIVE_HOSTS",
    "TDX_HOST_CACHE_SECONDS",
    "AKSHARE_WORKERS",
    "BAOSTOCK_WORKERS",
    "DATA_MEMORY_BUDGET_GB",
    "DATA_ESTIMATED_WORKER_MB",
    "DATA_REQUEST_DELAY",
    "DATA_MAX_CONSECUTIVE_ERRORS",
    "AGENT_PROVIDER",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "ANTHROPIC_API_KEY",
    "AGENT_MODEL",
    "AGENT_MAX_TOKENS",
    "FUTU_HOST",
    "FUTU_PORT",
}
CONFIG_KEYS = sorted(EXPECTED_KEYS | {"QUANT_CONFIG_FILE"})


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise AssertionError(f"{path.relative_to(ROOT)} has invalid line: {line}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Z_][A-Z0-9_]*$", key):
            raise AssertionError(f"{path.relative_to(ROOT)} has invalid key: {key}")
        if key in values:
            raise AssertionError(f"{path.relative_to(ROOT)} repeats key: {key}")
        values[key] = value.strip().strip('"').strip("'")
    return values


def assert_ports_in_url(value: str, port: int, label: str) -> None:
    if f":{port}" not in value:
        raise AssertionError(f"{label} does not reference port {port}: {value}")


def settings_from(path: Path):
    old_env = {key: os.environ.get(key) for key in CONFIG_KEYS}
    try:
        for key in CONFIG_KEYS:
            os.environ.pop(key, None)
        os.environ["QUANT_CONFIG_FILE"] = str(path)
        reset_settings()
        return get_settings()
    finally:
        reset_settings()
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> int:
    local = parse_env(LOCAL_ENV)
    prod = parse_env(PROD_ENV)

    for label, values in (("local", local), ("prod", prod)):
        missing = EXPECTED_KEYS - set(values)
        extra = set(values) - EXPECTED_KEYS
        if missing or extra:
            raise AssertionError(
                f"{label} env key mismatch: missing={sorted(missing)} extra={sorted(extra)}"
            )

    local_settings = settings_from(LOCAL_ENV)
    prod_settings = settings_from(PROD_ENV)

    if local_settings.app.backend_port != 8001 or local_settings.app.frontend_port != 5174:
        raise AssertionError("local env ports must match one-click development startup")
    if prod_settings.app.backend_port != 8001 or prod_settings.app.frontend_port != 8080:
        raise AssertionError("prod env ports must match docker-compose/nginx deployment")

    for origin in local_settings.app.cors_origins:
        assert_ports_in_url(origin, local_settings.app.frontend_port, "local CORS origin")
    for origin in prod_settings.app.cors_origins:
        assert_ports_in_url(origin, prod_settings.app.frontend_port, "prod CORS origin")

    quant_ps1 = (ROOT / "quant.ps1").read_text(encoding="utf-8")
    quant_sh = (ROOT / "quant.sh").read_text(encoding="utf-8")
    if '"8001"' not in quant_ps1 or '"5174"' not in quant_ps1:
        raise AssertionError("quant.ps1 defaults must include backend 8001 and frontend 5174")
    if 'BACKEND_PORT="${QUANT_BACKEND_PORT:-8001}"' not in quant_sh:
        raise AssertionError("quant.sh backend default port mismatch")
    if 'FRONTEND_PORT="${QUANT_FRONTEND_PORT:-5174}"' not in quant_sh:
        raise AssertionError("quant.sh frontend default port mismatch")

    print(
        json.dumps(
            {
                "status": "ok",
                "keys": len(EXPECTED_KEYS),
                "local_ports": [local_settings.app.backend_port, local_settings.app.frontend_port],
                "prod_ports": [prod_settings.app.backend_port, prod_settings.app.frontend_port],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    main()
