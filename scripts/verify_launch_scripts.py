from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def verify_windows_scripts() -> None:
    quant = read("quant.ps1")
    start = read("start-windows.cmd")
    stop = read("stop-windows.cmd")

    for command in ["setup", "start", "stop", "restart", "status", "logs"]:
        ensure(f'"{command}"' in quant, f"quant.ps1 missing command {command}")

    start_services = re.search(r"function Start-Services \{(?P<body>.*?)\n\}", quant, re.S)
    ensure(start_services is not None, "quant.ps1 missing Start-Services")
    body = start_services.group("body")
    ensure("Invoke-Setup" in body, "Start-Services does not bootstrap missing dependencies")
    ensure(
        body.index("Invoke-Setup") < body.index("Ensure-DemoData"),
        "Start-Services must bootstrap dependencies before seeding demo data",
    )
    ensure("Wait-Url $backendUrl" in body, "Start-Services does not wait for backend health")
    ensure("Wait-Url $frontendUrl" in body, "Start-Services does not wait for frontend")

    ensure('quant.ps1" start' in start, "start-windows.cmd does not invoke quant.ps1 start")
    ensure('quant.ps1" stop' in stop, "stop-windows.cmd does not invoke quant.ps1 stop")

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell:
        command = (
            "$errors=$null; "
            "[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw quant.ps1), [ref]$errors) | Out-Null; "
            "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
        )
        subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=ROOT,
            check=True,
        )


def verify_posix_scripts() -> None:
    quant = read("quant.sh")
    start = read("start-mac.command")
    stop = read("stop-mac.command")

    for command in ["setup", "start", "stop", "restart", "status", "logs", "doctor"]:
        ensure(f"{command})" in quant or f"{command}|" in quant, f"quant.sh missing command {command}")

    cmd_start = re.search(r"cmd_start\(\) \{(?P<body>.*?)\n\}", quant, re.S)
    ensure(cmd_start is not None, "quant.sh missing cmd_start")
    body = cmd_start.group("body")
    ensure("cmd_setup || return 1" in body, "cmd_start does not bootstrap dependencies")
    ensure(
        body.index("cmd_setup || return 1") < body.index("start_backend"),
        "cmd_start must bootstrap before starting backend",
    )
    ensure("wait_http \"$BACKEND_URL\"" in quant, "quant.sh does not wait for backend health")
    ensure("wait_http \"$FRONTEND_URL\"" in quant, "quant.sh does not wait for frontend")

    ensure("./quant.sh start" in start, "start-mac.command does not invoke quant.sh start")
    ensure("./quant.sh stop" in stop, "stop-mac.command does not invoke quant.sh stop")

    bash = shutil.which("bash")
    if bash:
        subprocess.run([bash, "-n", "quant.sh"], cwd=ROOT, check=True)
        subprocess.run([bash, "-n", "start-mac.command"], cwd=ROOT, check=True)
        subprocess.run([bash, "-n", "stop-mac.command"], cwd=ROOT, check=True)


def main() -> int:
    verify_windows_scripts()
    verify_posix_scripts()
    print(json.dumps({"status": "ok", "scripts_checked": 6}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise
