#!/usr/bin/env bash
# Cross-platform QuantLab service manager for macOS and Linux.
#
# Usage:
#   ./quant.sh setup
#   ./quant.sh start
#   ./quant.sh stop
#   ./quant.sh restart
#   ./quant.sh status
#   ./quant.sh logs [backend|frontend|all]
#   ./quant.sh doctor

set -uo pipefail

cd "$(dirname "$0")" || exit 1
ROOT_DIR="$(pwd -P)"
CONFIG_FILE="${QUANT_CONFIG_FILE:-$ROOT_DIR/config/quant.env}"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { printf "${CYAN}[quant]${NC} %s\n" "$*"; }
ok() { printf "${GREEN}[quant]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[quant]${NC} %s\n" "$*"; }
err() { printf "${RED}[quant]${NC} %s\n" "$*" >&2; }

mkdir -p "$PID_DIR" "$LOG_DIR"

load_config_file() {
    [[ -f "$CONFIG_FILE" ]] || return 0
    while IFS='=' read -r key value; do
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        [[ -n "$key" && "$key" != \#* ]] || continue
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        if [[ -z "${!key+x}" ]]; then
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
                value="${value:1:${#value}-2}"
            fi
            export "$key=$value"
        fi
    done <"$CONFIG_FILE"
}

load_config_file

BACKEND_HOST="${QUANT_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${QUANT_BACKEND_PORT:-8001}"
FRONTEND_HOST="${QUANT_FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${QUANT_FRONTEND_PORT:-5174}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/api/health"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

copy_default_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        mkdir -p "$(dirname "$CONFIG_FILE")"
        cp "$ROOT_DIR/config/quant.env.example" "$CONFIG_FILE"
        ok "Created config file: $CONFIG_FILE"
    fi
}

find_python_command() {
    local candidate
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && \
            "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
        then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    err "Python 3.10+ was not found. Install it with Homebrew: brew install python"
    return 1
}

venv_python() {
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
}

backend_ready_locally() {
    local python
    python="$(venv_python)"
    [[ -x "$python" ]] || return 1
    PYTHONPATH="$ROOT_DIR" QUANT_CONFIG_FILE="$CONFIG_FILE" \
        "$python" - <<'PY' >/dev/null 2>&1
import fastapi, pandas, pyarrow, uvicorn
import server.main
PY
}

setup_backend() {
    local python base_python code
    python="$(venv_python)"
    if [[ ! -x "$python" ]]; then
        if [[ -d "$ROOT_DIR/.venv" ]]; then
            warn "Existing .venv is not usable on this system; recreating it..."
            rm -rf "$ROOT_DIR/.venv"
        fi
        base_python="$(find_python_command)" || return 1
        info "Creating Python virtual environment..."
        "$base_python" -m venv "$ROOT_DIR/.venv" || return 1
    fi

    if backend_ready_locally; then
        ok "Backend dependencies: installed"
        return 0
    fi

    info "Installing backend dependencies..."
    "$python" -m pip install --disable-pip-version-check --prefer-binary -r "$REQUIREMENTS_FILE"
    code=$?
    if [[ "$code" -ne 0 ]]; then
        warn "Default package source failed; retrying official PyPI..."
        "$python" -m pip install --disable-pip-version-check --prefer-binary -r "$REQUIREMENTS_FILE" -i https://pypi.org/simple
        code=$?
    fi
    if [[ "$code" -ne 0 ]]; then
        warn "Official PyPI failed; retrying Tsinghua mirror..."
        "$python" -m pip install --disable-pip-version-check --prefer-binary -r "$REQUIREMENTS_FILE" -i https://pypi.tuna.tsinghua.edu.cn/simple
        code=$?
    fi
    if [[ "$code" -ne 0 ]]; then
        err "Backend dependency installation failed. Check your proxy or package index settings."
        return 1
    fi
    backend_ready_locally || {
        err "Backend packages installed, but import check failed."
        return 1
    }
}

setup_frontend() {
    if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
        err "Node.js/npm was not found. Install Node.js LTS from https://nodejs.org/ or run: brew install node"
        return 1
    fi
    if [[ -d "$ROOT_DIR/web/node_modules" ]]; then
        ok "Frontend dependencies: installed"
        return 0
    fi
    info "Installing frontend dependencies..."
    if [[ -f "$ROOT_DIR/web/package-lock.json" ]]; then
        (cd "$ROOT_DIR/web" && npm ci) || return 1
    else
        (cd "$ROOT_DIR/web" && npm install) || return 1
    fi
}

seed_demo_data() {
    info "Ensuring offline demo market data..."
    (cd "$ROOT_DIR" && PYTHONPATH="$ROOT_DIR" QUANT_CONFIG_FILE="$CONFIG_FILE" "$(venv_python)" scripts/seed_demo_data.py) || return 1
}

cmd_setup() {
    copy_default_config
    load_config_file
    setup_backend || return 1
    setup_frontend || return 1
    seed_demo_data || return 1
}

pid_alive() {
    local pid_file="$1" pid
    [[ -f "$pid_file" ]] || return 1
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

stop_process_tree() {
    local pid="$1" child
    if command -v pgrep >/dev/null 2>&1; then
        while read -r child; do
            [[ -n "$child" ]] || continue
            stop_process_tree "$child"
        done < <(pgrep -P "$pid" 2>/dev/null || true)
    fi
    kill -TERM "$pid" 2>/dev/null || true
}

port_pids() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port"/tcp 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' || true
    fi
}

port_open() {
    [[ -n "$(port_pids "$1")" ]]
}

http_ready() {
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS --max-time 2 "$url" >/dev/null 2>&1
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=2 --spider "$url" >/dev/null 2>&1
    else
        return 1
    fi
}

wait_http() {
    local url="$1" name="$2" log_file="$3"
    local i
    for ((i = 1; i <= 60; i++)); do
        http_ready "$url" && return 0
        sleep 0.5
    done
    err "$name failed to become ready: $url"
    [[ -f "$log_file" ]] && tail -n 40 "$log_file" >&2
    return 1
}

start_backend() {
    local python reload_args=()
    python="$(venv_python)"
    backend_ready_locally || setup_backend || return 1

    if http_ready "$BACKEND_URL"; then
        warn "Backend is already available at $BACKEND_URL"
        return 0
    fi
    if port_open "$BACKEND_PORT"; then
        err "Port $BACKEND_PORT is occupied, but backend health check failed."
        return 1
    fi

    [[ "${QUANT_RELOAD:-0}" == "1" ]] && reload_args=(--reload --reload-dir "$ROOT_DIR/server")
    info "Starting backend on port $BACKEND_PORT..."
    : >"$BACKEND_LOG"
    (
        cd "$ROOT_DIR" || exit 1
        PYTHONPATH="$ROOT_DIR" QUANT_CONFIG_FILE="$CONFIG_FILE" \
            nohup "$python" -m uvicorn server.main:app \
            --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
            "${reload_args[@]}" >>"$BACKEND_LOG" 2>&1 &
        echo "$!" >"$BACKEND_PID_FILE"
    )
    wait_http "$BACKEND_URL" "Backend" "$BACKEND_LOG" && ok "Backend ready: http://localhost:$BACKEND_PORT"
}

start_frontend() {
    local node vite
    setup_frontend || return 1
    node="$(command -v node)"
    vite="$ROOT_DIR/web/node_modules/vite/bin/vite.js"
    [[ -f "$vite" ]] || {
        err "Vite entrypoint not found. Reinstall frontend dependencies with: cd web && npm ci"
        return 1
    }

    if http_ready "$FRONTEND_URL"; then
        warn "Frontend is already available at $FRONTEND_URL"
        return 0
    fi
    if port_open "$FRONTEND_PORT"; then
        err "Port $FRONTEND_PORT is already occupied."
        return 1
    fi

    info "Starting frontend on port $FRONTEND_PORT..."
    : >"$FRONTEND_LOG"
    (
        cd "$ROOT_DIR/web" || exit 1
        QUANT_BACKEND_PORT="$BACKEND_PORT" \
            nohup "$node" "$vite" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
            >>"$FRONTEND_LOG" 2>&1 &
        echo "$!" >"$FRONTEND_PID_FILE"
    )
    wait_http "$FRONTEND_URL" "Frontend" "$FRONTEND_LOG" && ok "Frontend ready: http://localhost:$FRONTEND_PORT"
}

stop_by_pid_file() {
    local name="$1" pid_file="$2" pid i
    if pid_alive "$pid_file"; then
        pid="$(cat "$pid_file")"
        info "Stopping $name (PID $pid)..."
        stop_process_tree "$pid"
        for ((i = 0; i < 30; i++)); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.2
        done
        kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

stop_by_port() {
    local name="$1" port="$2" pid
    while read -r pid; do
        [[ -n "$pid" ]] || continue
        warn "Stopping leftover $name listener on port $port (PID $pid)..."
        stop_process_tree "$pid"
        sleep 0.5
        kill -KILL "$pid" 2>/dev/null || true
    done < <(port_pids "$port")
}

cmd_start() {
    echo
    copy_default_config
    load_config_file
    info "Starting Quant..."
    cmd_setup || return 1
    local failed=0
    start_backend || failed=1
    start_frontend || failed=1
    echo
    if ((failed)); then
        err "One or more services failed to start. Run: ./quant.sh logs all"
        return 1
    fi
    ok "Quant is ready"
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend:  http://localhost:$BACKEND_PORT"
    echo "  API docs: http://localhost:$BACKEND_PORT/docs"
    echo
}

cmd_stop() {
    echo
    stop_by_pid_file "Frontend" "$FRONTEND_PID_FILE"
    stop_by_pid_file "Backend" "$BACKEND_PID_FILE"
    stop_by_port "frontend" "$FRONTEND_PORT"
    stop_by_port "backend" "$BACKEND_PORT"
    echo
    if port_open "$FRONTEND_PORT" || port_open "$BACKEND_PORT"; then
        err "Some Quant ports are still occupied. Run: ./quant.sh status"
        return 1
    fi
    ok "Quant stopped"
}

service_status() {
    local name="$1" pid_file="$2" port="$3" url="$4" owner="none"
    pid_alive "$pid_file" && owner="pid $(cat "$pid_file")"
    if http_ready "$url"; then
        ok "$name: ready ($owner, port $port)"
    elif port_open "$port"; then
        warn "$name: port $port is open, but health check failed ($owner)"
    else
        err "$name: stopped"
    fi
}

cmd_status() {
    echo
    service_status "Backend" "$BACKEND_PID_FILE" "$BACKEND_PORT" "$BACKEND_URL"
    service_status "Frontend" "$FRONTEND_PID_FILE" "$FRONTEND_PORT" "$FRONTEND_URL"
    echo
}

cmd_logs() {
    case "${1:-backend}" in
        backend|back|b) tail -n 100 -f "$BACKEND_LOG" ;;
        frontend|front|f) tail -n 100 -f "$FRONTEND_LOG" ;;
        all|a) tail -n 100 -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
        *) err "Unknown log target: $1 (backend, frontend, all)"; return 1 ;;
    esac
}

cmd_doctor() {
    echo
    info "Environment check"
    local failed=0 python node_path
    python="$(venv_python)"
    if [[ -x "$python" ]]; then
        ok "Python venv: $($python --version 2>&1) ($python)"
    else
        warn "Python venv: missing; setup will create it"
    fi
    find_python_command >/dev/null || failed=1
    if node_path="$(command -v node 2>/dev/null)"; then
        ok "Node: $(node --version) ($node_path)"
    else
        err "Node: missing"
        failed=1
    fi
    command -v npm >/dev/null 2>&1 && ok "npm: $(npm --version)" || { err "npm: missing"; failed=1; }
    [[ -f "$CONFIG_FILE" ]] && ok "Configuration: $CONFIG_FILE" || warn "Configuration missing: setup will create $CONFIG_FILE"
    [[ -d "$ROOT_DIR/web/node_modules" ]] && ok "Frontend dependencies: installed" || warn "Frontend dependencies: missing"
    backend_ready_locally && ok "Backend dependencies: installed" || warn "Backend dependencies: missing"
    echo
    cmd_status
    return "$failed"
}

cmd_help() {
    cat <<EOF

Quant service manager

Usage:
  ./quant.sh <command>

Commands:
  setup                 Create config, Python venv, and install dependencies
  start                 Start backend and frontend
  stop                  Stop backend and frontend
  restart               Restart both services
  status                Show service and health status
  logs [target]         Follow logs: backend, frontend, or all
  doctor                Check Python, Node, dependencies, and services
  help                  Show this help

Environment:
  QUANT_CONFIG_FILE       Config file (default: config/quant.env)
  QUANT_BACKEND_PORT      Backend port (default: 8001)
  QUANT_FRONTEND_PORT     Frontend port (default: 5174)
  QUANT_RELOAD=1          Enable uvicorn auto-reload

EOF
}

case "${1:-help}" in
    setup) cmd_setup ;;
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_stop && sleep 1 && cmd_start ;;
    status) cmd_status ;;
    logs|log) cmd_logs "${2:-backend}" ;;
    doctor) cmd_doctor ;;
    help|-h|--help) cmd_help ;;
    *) err "Unknown command: $1"; cmd_help; exit 1 ;;
esac
