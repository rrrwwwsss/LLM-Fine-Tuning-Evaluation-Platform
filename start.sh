#!/bin/bash
# start.sh - 一键启动（Linux）
# 用法: ./start.sh            # 前台运行
#       ./start.sh --bg       # 后台运行

set -e

# 激活 conda 环境
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate Qwen311 2>/dev/null || source activate Qwen311 2>/dev/null || echo "警告: 无法激活 Qwen311 环境"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PID_FILE="$ROOT_DIR/.backend.pid"
LOG_DIR="$ROOT_DIR/logs"

# Linux server directories exposed by the web directory picker. Callers may
# still override this before startup, but the project default is /HTC/rws.
export SERVER_BROWSE_ROOTS="${SERVER_BROWSE_ROOTS:-/HTC/rws}"

IFS=',' read -ra BROWSE_ROOT_LIST <<< "$SERVER_BROWSE_ROOTS"
for BROWSE_ROOT in "${BROWSE_ROOT_LIST[@]}"; do
    if [ ! -d "$BROWSE_ROOT" ]; then
        echo "警告: Linux 目录白名单不存在: $BROWSE_ROOT"
    elif [ ! -r "$BROWSE_ROOT" ] || [ ! -x "$BROWSE_ROOT" ]; then
        echo "警告: 当前用户无权读取或进入白名单目录: $BROWSE_ROOT"
        echo "      当前用户: $(id -un)"
        ls -ld "$BROWSE_ROOT" 2>/dev/null || true
    else
        echo "Linux 目录白名单可用: $BROWSE_ROOT"
    fi
done

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"
echo "服务器目录白名单配置: $SERVER_BROWSE_ROOTS"

is_project_backend() {
    local CHECK_PID="$1"
    [ -n "$CHECK_PID" ] || return 1
    kill -0 "$CHECK_PID" 2>/dev/null || return 1
    [ "$(readlink -f "/proc/$CHECK_PID/cwd" 2>/dev/null)" = "$ROOT_DIR/backend" ] || return 1
    tr '\000' ' ' < "/proc/$CHECK_PID/cmdline" 2>/dev/null | grep -q "run_server.py.*--prod"
}

find_project_backend() {
    local CANDIDATE
    for CANDIDATE in $(pgrep -f "run_server.py[[:space:]]+--prod" 2>/dev/null || true); do
        if is_project_backend "$CANDIDATE"; then
            echo "$CANDIDATE"
            return 0
        fi
    done
    return 1
}

EXISTING_PID=""
if [ -f "$PID_FILE" ]; then
    SAVED_PID="$(tr -dc '0-9' < "$PID_FILE")"
    if is_project_backend "$SAVED_PID"; then
        EXISTING_PID="$SAVED_PID"
    else
        echo "发现失效 PID 文件，正在修复: ${SAVED_PID:-空}"
        rm -f "$PID_FILE"
    fi
fi
if [ -z "$EXISTING_PID" ]; then
    EXISTING_PID="$(find_project_backend || true)"
fi
if [ -n "$EXISTING_PID" ]; then
    printf '%s\n' "$EXISTING_PID" > "$PID_FILE"
    echo "系统已经运行，PID: $EXISTING_PID"
    echo "如需重启，请先执行 ./stop.sh"
    exit 1
fi
if (echo > /dev/tcp/127.0.0.1/18080) >/dev/null 2>&1; then
    echo "无法启动: 端口 18080 已被其他进程占用"
    exit 1
fi

# 1. 安装前端依赖
echo "[1/3] 安装前端依赖..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi

# 2. 构建前端
echo "[2/3] 构建前端..."
npm run build
echo "      前端构建完成: frontend/dist/"

# 3. 启动后端
cd "$ROOT_DIR/backend"
echo "[3/3] 启动后端服务 (端口 18080)..."

if [ "$1" = "--bg" ]; then
    nohup python run_server.py --prod > "$LOG_DIR/backend.log" 2>&1 &
    BGPID=$!
    printf '%s\n' "$BGPID" > "$PID_FILE"
    sleep 1
    if ! is_project_backend "$BGPID"; then
        echo "后端启动失败，最近日志如下:"
        tail -n 30 "$LOG_DIR/backend.log" 2>/dev/null || true
        rm -f "$PID_FILE"
        exit 1
    fi
    echo ""
    echo "======================================"
    echo "  系统已后台启动 (PID: $BGPID)"
    echo "  后端地址: http://localhost:18080"
    echo "  日志文件: logs/backend.log"
    echo "  停止命令: ./stop.sh"
    echo "======================================"
else
    echo "  前台运行中... (按 Ctrl+C 停止)"
    echo "  访问地址: http://localhost:18080"
    echo ""
    python run_server.py --prod &
    FGPID=$!
    printf '%s\n' "$FGPID" > "$PID_FILE"
    trap 'kill "$FGPID" 2>/dev/null || true' INT TERM
    set +e
    wait "$FGPID"
    EXIT_CODE=$?
    set -e
    rm -f "$PID_FILE"
    trap - INT TERM
    exit "$EXIT_CODE"
fi
