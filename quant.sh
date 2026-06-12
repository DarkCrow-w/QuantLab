#!/usr/bin/env bash
# Quant development service manager.
#
# Usage:
#   ./quant.sh start
#   ./quant.sh stop
#   ./quant.sh restart
#   ./quant.sh status
#   ./quant.sh logs [backend|frontend|all]
#   ./quant.sh doctor

set -uo pipefail

SCRIPT_PATH="$(readlink -f "$0")"
ROOT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
CONFIG_FILE="${QUANT_CONFIG_FILE:-$ROOT_DIR/config/quant.env}"

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

PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

BACKEND_UNIT="quant-backend.service"
FRONTEND_UNIT="quant-frontend.service"
BACKEND_HOST="${QUANT_BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${QUANT_BACKEND_PORT:-8000}"
FRONTEND_HOST="${QUANT_FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${QUANT_FRONTEND_PORT:-5173}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/api/health"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}[quant]${NC} $*"; }
ok() { echo -e "${GREEN}[quant]${NC} $*"; }
warn() { echo -e "${YELLOW}[quant]${NC} $*"; }
err() { echo -e "${RED}[quant]${NC} $*" >&2; }

mkdir -p "$PID_DIR" "$LOG_DIR"

have_systemd() {
    command -v systemctl >/dev/null 2>&1 &&
        command -v systemd-run >/dev/null 2>&1 &&
        [[ "$(ps -p 1 -o comm= 2>/dev/null | xargs)" == "systemd" ]]
}

unit_exists() {
    [[ "$(systemctl show "$1" -p LoadState --value 2>/dev/null)" != "not-found" ]]
}

unit_active() {
    systemctl is-active --quiet "$1" 2>/dev/null
}

pid_alive() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 1
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

pid_belongs_to_quant() {
    local pid="$1"
    local cmdline
    cmdline="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    [[ "$cmdline" == *"$ROOT_DIR"* ]] ||
        [[ "$cmdline" == *"server.main:app"* ]] ||
        [[ "$cmdline" == *"vite"* ]] ||
        [[ "$cmdline" == *"pnpm dev"* ]] ||
        [[ "$cmdline" == *"npm run dev"* ]]
}

stop_process_tree() {
    local pid="$1"
    local child
    while read -r child; do
        [[ -n "$child" ]] || continue
        stop_process_tree "$child"
    done < <(pgrep -P "$pid" 2>/dev/null || true)
    kill -TERM "$pid" 2>/dev/null || true
}

port_open() {
    local port="$1"
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"
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
    local attempts=40
    for ((i = 1; i <= attempts; i++)); do
        if http_ready "$url"; then
            return 0
        fi
        sleep 0.5
    done
    err "$name failed to become ready: $url"
    [[ -f "$log_file" ]] && tail -n 30 "$log_file" >&2
    return 1
}

setup_node() {
    export FNM_DIR="${FNM_DIR:-$HOME/.local/share/fnm}"

    if command -v fnm >/dev/null 2>&1; then
        eval "$(fnm env --shell bash 2>/dev/null)" || true
    elif [[ -d "$FNM_DIR/node-versions" ]]; then
        local latest_node
        latest_node="$(
            find "$FNM_DIR/node-versions" -mindepth 2 -maxdepth 2 \
                -type d -name installation 2>/dev/null |
                sort -V | tail -n 1
        )"
        if [[ -n "$latest_node" && -d "$latest_node/bin" ]]; then
            export PATH="$latest_node/bin:$PATH"
        fi
    fi
}

find_python() {
    local python="$ROOT_DIR/.venv/bin/python"
    if [[ ! -x "$python" ]]; then
        err "Python virtual environment not found: $python"
        err "Create it with: python3 -m venv .venv && .venv/bin/pip install -e ."
        return 1
    fi
    if ! "$python" -c "import uvicorn, fastapi" >/dev/null 2>&1; then
        err "The virtual environment is missing uvicorn or fastapi."
        err "Install project dependencies with: $python -m pip install -e ."
        return 1
    fi
    printf '%s\n' "$python"
}

find_frontend_runner() {
    local runner
    if command -v pnpm >/dev/null 2>&1; then
        runner="$(command -v pnpm)"
        if [[ "$runner" != /mnt/* ]]; then
            printf '%s\n' "$runner"
            return 0
        fi
    fi
    if command -v npm >/dev/null 2>&1; then
        runner="$(command -v npm)"
        if [[ "$runner" != /mnt/* ]]; then
            printf '%s\n' "$runner"
            return 0
        fi
    fi
    return 1
}

find_node() {
    local node_path
    if command -v node >/dev/null 2>&1; then
        node_path="$(command -v node)"
        if [[ "$node_path" != /mnt/* ]]; then
            printf '%s\n' "$node_path"
            return 0
        fi
    fi

    node_path="$(
        find "$HOME/.vscode-server/bin" "$HOME/.vscode-remote-containers/bin" \
            -mindepth 2 -maxdepth 2 -type f -name node -executable 2>/dev/null |
            sort -V | tail -n 1
    )"
    if [[ -n "$node_path" ]]; then
        printf '%s\n' "$node_path"
        return 0
    fi
    err "A Linux Node.js runtime was not found."
    err "Install Node.js inside WSL, or configure fnm under ~/.local/share/fnm."
    return 1
}

stop_stale_unit() {
    local unit="$1"
    if have_systemd && unit_exists "$unit" && ! unit_active "$unit"; then
        systemctl reset-failed "$unit" >/dev/null 2>&1 || true
        systemctl stop "$unit" >/dev/null 2>&1 || true
    fi
}

start_backend() {
    local python
    python="$(find_python)" || return 1

    if http_ready "$BACKEND_URL"; then
        warn "Backend is already available at $BACKEND_URL"
        return 0
    fi
    if port_open "$BACKEND_PORT"; then
        err "Port $BACKEND_PORT is occupied, but the backend health check failed."
        return 1
    fi

    info "Starting backend on port $BACKEND_PORT..."
    : >"$BACKEND_LOG"

    local reload_args=()
    if [[ "${QUANT_RELOAD:-0}" == "1" ]]; then
        reload_args=(--reload --reload-dir "$ROOT_DIR/server")
    fi

    if have_systemd; then
        stop_stale_unit "$BACKEND_UNIT"
        local service_env_args=(--setenv="PYTHONPATH=$ROOT_DIR")
        if [[ -f "$CONFIG_FILE" ]]; then
            while IFS='=' read -r key _; do
                key="${key#"${key%%[![:space:]]*}"}"
                key="${key%"${key##*[![:space:]]}"}"
                [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
                service_env_args+=(--setenv="$key=${!key-}")
            done <"$CONFIG_FILE"
        fi
        local proxy_key
        for proxy_key in \
            HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY \
            http_proxy https_proxy all_proxy no_proxy; do
            if [[ -n "${!proxy_key-}" ]]; then
                service_env_args+=(--setenv="$proxy_key=${!proxy_key}")
            fi
        done
        service_env_args+=(--setenv="QUANT_CONFIG_FILE=$CONFIG_FILE")
        systemd-run \
            --unit="${BACKEND_UNIT%.service}" \
            --property="WorkingDirectory=$ROOT_DIR" \
            --property="Restart=on-failure" \
            --property="MemoryHigh=${QUANT_MEMORY_HIGH:-9G}" \
            --property="MemoryMax=${QUANT_MEMORY_MAX:-10G}" \
            --property="StandardOutput=append:$BACKEND_LOG" \
            --property="StandardError=append:$BACKEND_LOG" \
            "${service_env_args[@]}" \
            "$python" -m uvicorn server.main:app \
            --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
            "${reload_args[@]}" >/dev/null 2>&1
    else
        (
            cd "$ROOT_DIR" || exit 1
            nohup setsid "$python" -m uvicorn server.main:app \
                --host "$BACKEND_HOST" --port "$BACKEND_PORT" \
                "${reload_args[@]}" >>"$BACKEND_LOG" 2>&1 &
            echo "$!" >"$BACKEND_PID_FILE"
        )
    fi

    if wait_http "$BACKEND_URL" "Backend" "$BACKEND_LOG"; then
        ok "Backend ready: http://localhost:$BACKEND_PORT"
    else
        return 1
    fi
}

start_frontend() {
    local runner node vite
    setup_node
    node="$(find_node)" || return 1
    vite="$ROOT_DIR/web/node_modules/vite/bin/vite.js"

    if http_ready "$FRONTEND_URL"; then
        warn "Frontend is already available at $FRONTEND_URL"
        return 0
    fi
    if port_open "$FRONTEND_PORT"; then
        err "Port $FRONTEND_PORT is already occupied."
        return 1
    fi
    if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
        runner="$(find_frontend_runner)" || {
            err "Frontend dependencies are missing and no Linux npm/pnpm was found."
            return 1
        }
        info "Installing frontend dependencies..."
        (cd "$ROOT_DIR/web" && "$runner" install) || return 1
    fi
    if [[ ! -f "$vite" ]]; then
        err "Vite entrypoint not found: $vite"
        err "Reinstall frontend dependencies inside WSL."
        return 1
    fi

    info "Starting frontend on port $FRONTEND_PORT..."
    : >"$FRONTEND_LOG"

    if have_systemd; then
        stop_stale_unit "$FRONTEND_UNIT"
        systemd-run \
            --unit="${FRONTEND_UNIT%.service}" \
            --property="WorkingDirectory=$ROOT_DIR/web" \
            --property="Restart=on-failure" \
            --property="StandardOutput=append:$FRONTEND_LOG" \
            --property="StandardError=append:$FRONTEND_LOG" \
            --setenv="PATH=$PATH" \
            "$node" "$vite" --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
            >/dev/null 2>&1
    else
        (
            cd "$ROOT_DIR/web" || exit 1
            nohup setsid "$node" "$vite" \
                --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
                >>"$FRONTEND_LOG" 2>&1 &
            echo "$!" >"$FRONTEND_PID_FILE"
        )
    fi

    if wait_http "$FRONTEND_URL" "Frontend" "$FRONTEND_LOG"; then
        ok "Frontend ready: http://localhost:$FRONTEND_PORT"
    else
        return 1
    fi
}

stop_one() {
    local name="$1" unit="$2" pid_file="$3"
    local stopped=0

    if have_systemd && unit_exists "$unit"; then
        if unit_active "$unit"; then
            info "Stopping $name..."
            systemctl stop "$unit" >/dev/null 2>&1 || true
            stopped=1
        fi
        systemctl reset-failed "$unit" >/dev/null 2>&1 || true
    fi

    if pid_alive "$pid_file"; then
        local pid
        pid="$(cat "$pid_file")"
        if pid_belongs_to_quant "$pid"; then
            info "Stopping $name (PID $pid)..."
            stop_process_tree "$pid"
            for ((i = 0; i < 20; i++)); do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.2
            done
            if kill -0 "$pid" 2>/dev/null; then
                kill -KILL "$pid" 2>/dev/null || true
            fi
            stopped=1
        else
            warn "Ignoring stale $name PID file: $pid does not belong to Quant"
        fi
    fi
    rm -f "$pid_file"

    if ((stopped)); then
        ok "$name stopped"
    else
        info "$name is not running"
    fi
}

service_status() {
    local name="$1" unit="$2" pid_file="$3" port="$4" url="$5"
    local owner="none"
    if have_systemd && unit_active "$unit"; then
        owner="systemd"
    elif pid_alive "$pid_file"; then
        owner="pid $(cat "$pid_file")"
    fi

    if http_ready "$url"; then
        ok "$name: ready ($owner, port $port)"
    elif port_open "$port"; then
        warn "$name: port $port is open, but health check failed ($owner)"
    else
        err "$name: stopped"
    fi
}

cmd_start() {
    echo
    info "Starting Quant..."
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
    stop_one "Frontend" "$FRONTEND_UNIT" "$FRONTEND_PID_FILE"
    stop_one "Backend" "$BACKEND_UNIT" "$BACKEND_PID_FILE"
    echo
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    echo
    service_status "Backend" "$BACKEND_UNIT" "$BACKEND_PID_FILE" \
        "$BACKEND_PORT" "$BACKEND_URL"
    service_status "Frontend" "$FRONTEND_UNIT" "$FRONTEND_PID_FILE" \
        "$FRONTEND_PORT" "$FRONTEND_URL"
    echo
}

follow_file_logs() {
    local target="$1"
    case "$target" in
    backend | back | b) tail -n 100 -f "$BACKEND_LOG" ;;
    frontend | front | f) tail -n 100 -f "$FRONTEND_LOG" ;;
    all | a) tail -n 100 -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
    *)
        err "Unknown log target: $target (backend, frontend, all)"
        return 1
        ;;
    esac
}

cmd_logs() {
    follow_file_logs "${1:-backend}"
}

cmd_doctor() {
    echo
    info "Environment check"
    local failed=0
    local python runner

    if python="$(find_python)"; then
        ok "Python: $("$python" --version 2>&1) ($python)"
        ok "Uvicorn: $("$python" -c 'import uvicorn; print(uvicorn.__version__)')"
    else
        failed=1
    fi

    setup_node
    if node_path="$(find_node)"; then
        ok "Node: $("$node_path" --version) ($node_path)"
        if runner="$(find_frontend_runner)"; then
            ok "Frontend package runner: $runner"
        else
            warn "Linux npm/pnpm not found; existing node_modules can still run."
        fi
    else
        failed=1
    fi

    if have_systemd; then
        ok "Process manager: systemd"
    else
        warn "Process manager: nohup fallback"
    fi

    [[ -d "$ROOT_DIR/web/node_modules" ]] \
        && ok "Frontend dependencies: installed" \
        || warn "Frontend dependencies: will be installed on start"

    if [[ -f "$CONFIG_FILE" ]]; then
        ok "Configuration: $CONFIG_FILE"
        [[ -n "${TUSHARE_TOKEN:-}" ]] \
            && ok "TuShare token: configured" \
            || warn "TuShare token: missing"
        case "${AGENT_PROVIDER:-deepseek}" in
            deepseek)
                [[ -n "${DEEPSEEK_API_KEY:-}" ]] \
                    && ok "AI agent: DeepSeek configured" \
                    || warn "DeepSeek API key: missing (AI assistant unavailable)"
                ;;
            anthropic)
                [[ -n "${ANTHROPIC_API_KEY:-}" ]] \
                    && ok "AI agent: Anthropic configured" \
                    || warn "Anthropic API key: missing (AI assistant unavailable)"
                ;;
            *)
                warn "AI agent provider is unsupported: ${AGENT_PROVIDER:-}"
                ;;
        esac
    else
        warn "Configuration missing: $CONFIG_FILE"
        warn "Create it from config/quant.env.example"
    fi

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
  start                 Start backend and frontend
  stop                  Stop backend and frontend
  restart               Restart both services
  status                Show service and health status
  logs [target]         Follow logs: backend, frontend, or all
  log [target]          Alias for logs
  doctor                Check Python, Node, dependencies, and services
  help                  Show this help

Environment:
  QUANT_CONFIG_FILE     Config file (default: config/quant.env)
  QUANT_BACKEND_PORT     Backend port (default: 8000)
  QUANT_FRONTEND_PORT    Frontend port (default: 5173)
  QUANT_RELOAD=1         Enable uvicorn auto-reload

EOF
}

case "${1:-help}" in
start) cmd_start ;;
stop) cmd_stop ;;
restart) cmd_restart ;;
status) cmd_status ;;
logs | log) cmd_logs "${2:-backend}" ;;
doctor) cmd_doctor ;;
help | -h | --help) cmd_help ;;
*)
    err "Unknown command: $1"
    cmd_help
    exit 1
    ;;
esac
