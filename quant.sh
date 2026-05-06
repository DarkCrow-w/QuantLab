#!/usr/bin/env bash
# ──────────────────────────────────────────────
#  quant — 量化回测平台启动工具
#  用法:
#    quant start   启动前后端
#    quant stop    停止前后端
#    quant restart 重启
#    quant status  查看运行状态
#    quant log     查看后端日志
# ──────────────────────────────────────────────
set -uo pipefail

SCRIPT_PATH="$(readlink -f "$0")"
ROOT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[quant]${NC} $*"; }
ok()    { echo -e "${GREEN}[quant]${NC} $*"; }
warn()  { echo -e "${YELLOW}[quant]${NC} $*"; }
err()   { echo -e "${RED}[quant]${NC} $*"; }

mkdir -p "$PID_DIR" "$LOG_DIR"

# ── 检查进程是否存活 ──
is_alive() {
    local pidfile="$1"
    [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

# ── 等待端口就绪 ──
wait_port() {
    local port=$1 name=$2 max=30
    for ((i=1; i<=max; i++)); do
        if ss -tlnp 2>/dev/null | grep -q ":${port} " || \
           netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
            return 0
        fi
        sleep 0.5
    done
    warn "${name} 端口 ${port} 未在 ${max}s 内就绪，请检查日志"
    return 1
}

# ── 解析 fnm 环境 ──
setup_node() {
    export FNM_DIR="$HOME/.local/share/fnm"
    if [[ -d "$FNM_DIR" ]]; then
        export PATH="$FNM_DIR:$PATH"
        eval "$(fnm env --shell bash 2>/dev/null)" || true
    fi
}

# ── 启动后端 ──
start_backend() {
    if is_alive "$BACKEND_PID"; then
        warn "后端已在运行 (PID $(cat "$BACKEND_PID"))"
        return 0
    fi
    info "启动后端 (uvicorn :${BACKEND_PORT}) ..."
    cd "$ROOT_DIR"
    nohup "$ROOT_DIR/.venv/bin/uvicorn" server.main:app \
        --host 0.0.0.0 --port "$BACKEND_PORT" \
        --reload --reload-dir server \
        > "$BACKEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$BACKEND_PID"
    if wait_port "$BACKEND_PORT" "后端"; then
        ok "后端已启动 (PID ${pid})"
    fi
}

# ── 启动前端 ──
start_frontend() {
    if is_alive "$FRONTEND_PID"; then
        warn "前端已在运行 (PID $(cat "$FRONTEND_PID"))"
        return 0
    fi
    setup_node
    if ! command -v pnpm &>/dev/null; then
        err "未找到 pnpm，请先安装 Node.js + pnpm"
        return 1
    fi
    info "启动前端 (vite :${FRONTEND_PORT}) ..."
    cd "$ROOT_DIR/web"
    nohup pnpm dev --host 0.0.0.0 > "$FRONTEND_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$FRONTEND_PID"
    if wait_port "$FRONTEND_PORT" "前端"; then
        ok "前端已启动 (PID ${pid})"
    fi
}

# ── 停止单个服务 ──
stop_service() {
    local pidfile="$1" name="$2"
    if ! is_alive "$pidfile"; then
        info "${name} 未运行"
        return 0
    fi
    local pid
    pid=$(cat "$pidfile")
    info "停止 ${name} (PID ${pid}) ..."
    # 先发 TERM 给整个进程组，再清理
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    # 等待退出
    for ((i=0; i<20; i++)); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.3
    done
    # 如果还没退，强杀
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pidfile"
    ok "${name} 已停止"
}

# ── 命令 ──
cmd_start() {
    echo ""
    echo -e "  ${CYAN}╔══════════════════════════════════╗${NC}"
    echo -e "  ${CYAN}║${NC}      量化回测平台 启动中...      ${CYAN}║${NC}"
    echo -e "  ${CYAN}╚══════════════════════════════════╝${NC}"
    echo ""
    start_backend
    start_frontend
    echo ""
    ok "全部就绪!"
    echo -e "  前端: ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
    echo -e "  后端: ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
    echo -e "  文档: ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
    echo ""
}

cmd_stop() {
    echo ""
    stop_service "$FRONTEND_PID" "前端"
    stop_service "$BACKEND_PID" "后端"
    # 确保端口释放
    fuser -k "${BACKEND_PORT}/tcp" 2>/dev/null || true
    fuser -k "${FRONTEND_PORT}/tcp" 2>/dev/null || true
    echo ""
    ok "全部已停止"
    echo ""
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    echo ""
    if is_alive "$BACKEND_PID"; then
        ok "后端: 运行中 (PID $(cat "$BACKEND_PID"), 端口 ${BACKEND_PORT})"
    else
        err "后端: 未运行"
    fi
    if is_alive "$FRONTEND_PID"; then
        ok "前端: 运行中 (PID $(cat "$FRONTEND_PID"), 端口 ${FRONTEND_PORT})"
    else
        err "前端: 未运行"
    fi
    echo ""
}

cmd_log() {
    local target="${1:-backend}"
    case "$target" in
        backend|back|b)  tail -f "$BACKEND_LOG" ;;
        frontend|front|f) tail -f "$FRONTEND_LOG" ;;
        all|a)
            tail -f "$BACKEND_LOG" "$FRONTEND_LOG"
            ;;
        *)
            err "未知日志目标: $target (可选: backend, frontend, all)"
            ;;
    esac
}

cmd_help() {
    echo ""
    echo -e "  ${CYAN}quant${NC} — 量化回测平台启动工具"
    echo ""
    echo "  用法: quant <command>"
    echo ""
    echo "  命令:"
    echo -e "    ${GREEN}start${NC}     启动前后端服务"
    echo -e "    ${GREEN}stop${NC}      停止所有服务"
    echo -e "    ${GREEN}restart${NC}   重启所有服务"
    echo -e "    ${GREEN}status${NC}    查看运行状态"
    echo -e "    ${GREEN}log${NC}       查看日志 (backend|frontend|all)"
    echo -e "    ${GREEN}help${NC}      显示帮助"
    echo ""
}

# ── 入口 ──
case "${1:-help}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    log)     cmd_log "${2:-backend}" ;;
    help|-h|--help) cmd_help ;;
    *)
        err "未知命令: $1"
        cmd_help
        exit 1
        ;;
esac
