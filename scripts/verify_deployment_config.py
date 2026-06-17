from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def assert_file(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"missing deployment file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"{label} is missing required text: {needle}")


def main() -> None:
    compose_path = ROOT / "docker-compose.yml"
    backend_dockerfile = ROOT / "Dockerfile"
    frontend_dockerfile = ROOT / "web" / "Dockerfile"
    nginx_conf = ROOT / "web" / "nginx.conf"
    prod_env = ROOT / "config" / "quant.prod.env.example"

    compose = yaml.safe_load(assert_file(compose_path))
    backend_df = assert_file(backend_dockerfile)
    frontend_df = assert_file(frontend_dockerfile)
    nginx = assert_file(nginx_conf)
    env_text = assert_file(prod_env)
    dockerignore = assert_file(ROOT / ".dockerignore")

    services = compose.get("services", {})
    for service in ("backend", "frontend"):
        if service not in services:
            raise SystemExit(f"docker-compose.yml missing service: {service}")

    backend = services["backend"]
    frontend = services["frontend"]
    if backend.get("healthcheck") is None:
        raise SystemExit("backend service must define healthcheck")
    if frontend.get("healthcheck") is None:
        raise SystemExit("frontend service must define healthcheck")
    if "quantlab-data" not in compose.get("volumes", {}):
        raise SystemExit("docker-compose.yml must define quantlab-data volume")
    if "8080:80" not in (frontend.get("ports") or []):
        raise SystemExit("frontend service must expose 8080:80")

    assert_contains(backend_df, "uvicorn", "backend Dockerfile")
    assert_contains(backend_df, "/api/health", "backend Dockerfile")
    assert_contains(frontend_df, "npm run build", "frontend Dockerfile")
    assert_contains(frontend_df, "nginx", "frontend Dockerfile")
    assert_contains(nginx, "proxy_pass http://backend:8001/api/", "nginx.conf")
    assert_contains(nginx, "proxy_pass http://backend:8001/api/agent/chat", "nginx.conf")
    assert_contains(env_text, "QUANT_CORS_ORIGINS=http://localhost:8080", "prod env")
    assert_contains(dockerignore, "data", ".dockerignore")
    assert_contains(dockerignore, "web/node_modules", ".dockerignore")

    docker = shutil.which("docker")
    compose_available = False
    if docker:
        result = subprocess.run(
            [docker, "compose", "version", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        compose_available = result.returncode == 0
        if compose_available:
            subprocess.run(
                [docker, "compose", "-f", str(compose_path), "config", "--quiet"],
                cwd=ROOT,
                check=True,
            )

    print(
        json.dumps(
            {
                "status": "ok",
                "files_checked": [
                    "Dockerfile",
                    "web/Dockerfile",
                    "web/nginx.conf",
                    "docker-compose.yml",
                    "config/quant.prod.env.example",
                    ".dockerignore",
                ],
                "docker_compose_validated": compose_available,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
