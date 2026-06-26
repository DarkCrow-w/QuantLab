from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_config() -> dict[str, str]:
    path = ROOT / "config" / "quant.env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request(url: str, timeout: float = 3.0) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def wait_url(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            status, _text = request(url)
            if status == 200:
                return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def run_quant(command: str, timeout: float = 240.0) -> subprocess.CompletedProcess[str]:
    shell = powershell()
    if not shell:
        raise RuntimeError("PowerShell is not available")
    return subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "quant.ps1"),
            command,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def start_quant_background() -> subprocess.Popen[str]:
    shell = powershell()
    if not shell:
        raise RuntimeError("PowerShell is not available")
    return subprocess.Popen(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "quant.ps1"),
            "start",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def port_listening(port: int) -> bool:
    if os.name != "nt":
        return False
    command = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1"
    )
    shell = powershell()
    if not shell:
        return False
    result = subprocess.run(
        [shell, "-NoProfile", "-Command", command],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return bool(result.stdout.strip())


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"status": "skipped", "reason": "Windows-only launch smoke"}, ensure_ascii=False))
        return 0
    if not powershell():
        print(json.dumps({"status": "skipped", "reason": "PowerShell is not available"}, ensure_ascii=False))
        return 0

    config = read_config()
    backend_port = int(config.get("QUANT_BACKEND_PORT") or 8001)
    frontend_port = int(config.get("QUANT_FRONTEND_PORT") or 5174)
    backend_url = f"http://127.0.0.1:{backend_port}/api/health"
    frontend_url = f"http://127.0.0.1:{frontend_port}"

    if port_listening(backend_port) or port_listening(frontend_port):
        raise RuntimeError(
            f"Refusing launch smoke because port {backend_port} or {frontend_port} is already listening"
        )

    started = False
    starter: subprocess.Popen[str] | None = None
    try:
        starter = start_quant_background()
        started = True
        wait_url(backend_url, 60)
        wait_url(frontend_url, 60)

        status = run_quant("status", timeout=60.0)
        if status.returncode != 0:
            raise RuntimeError(f"quant.ps1 status failed:\nSTDOUT:\n{status.stdout}\nSTDERR:\n{status.stderr}")

        _code, health = request(backend_url)
        if '"status":"ok"' not in health.replace(" ", ""):
            raise AssertionError(f"unexpected backend health body: {health[:200]}")

        print(
            json.dumps(
                {
                    "status": "ok",
                    "backend": backend_url,
                    "frontend": frontend_url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        if started:
            stop = run_quant("stop", timeout=120.0)
            if stop.returncode != 0:
                print(
                    json.dumps(
                        {
                            "status": "cleanup_failed",
                            "stdout": stop.stdout,
                            "stderr": stop.stderr,
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
        if starter is not None and starter.poll() is None:
            starter.terminate()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise
