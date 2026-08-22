#!/bin/bash
# status.sh - 查看系统运行状态

ROOT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PID_FILE="$ROOT_DIR/.backend.pid"

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

echo "======================================"
echo "  LLM 微调评测平台 - 运行状态"
echo "======================================"

PID=""
if [ -f "$PID_FILE" ]; then
    SAVED_PID="$(tr -dc '0-9' < "$PID_FILE")"
    if is_project_backend "$SAVED_PID"; then
        PID="$SAVED_PID"
    else
        echo "  检测到失效 PID 文件: ${SAVED_PID:-空}，正在重新识别..."
        rm -f "$PID_FILE"
    fi
fi
if [ -z "$PID" ]; then
    PID="$(find_project_backend || true)"
    if [ -n "$PID" ]; then
        printf '%s\n' "$PID" > "$PID_FILE"
        echo "  已自动修复 PID 文件"
    fi
fi
if [ -n "$PID" ]; then
    echo "  后端进程: 运行中 (PID: $PID)"
    echo "  端口: 18080"
else
    echo "  后端进程: 未运行"
fi

echo ""
echo "  日志文件: logs/backend.log"
echo "  启动命令: ./start.sh --bg"
echo "  停止命令: ./stop.sh"
echo "======================================"
