#!/bin/bash
# stop.sh - 精确停止当前项目的 Linux 后端及其子进程

ROOT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
PID_FILE="$ROOT_DIR/.backend.pid"

is_project_backend() {
    local CHECK_PID="$1"
    [ -n "$CHECK_PID" ] || return 1
    kill -0 "$CHECK_PID" 2>/dev/null || return 1
    [ "$(readlink -f "/proc/$CHECK_PID/cwd" 2>/dev/null)" = "$ROOT_DIR/backend" ] || return 1
    tr '\000' ' ' < "/proc/$CHECK_PID/cmdline" 2>/dev/null | grep -q "run_server.py.*--prod"
}

find_project_backends() {
    local CANDIDATE
    for CANDIDATE in $(pgrep -f "run_server.py[[:space:]]+--prod" 2>/dev/null || true); do
        if is_project_backend "$CANDIDATE"; then
            echo "$CANDIDATE"
        fi
    done
}

collect_descendants() {
    local PARENT_PID="$1"
    local CHILD_PID
    for CHILD_PID in $(pgrep -P "$PARENT_PID" 2>/dev/null || true); do
        collect_descendants "$CHILD_PID"
        echo "$CHILD_PID"
    done
}

TARGET_PIDS=()
if [ -f "$PID_FILE" ]; then
    SAVED_PID="$(tr -dc '0-9' < "$PID_FILE")"
    if is_project_backend "$SAVED_PID"; then
        TARGET_PIDS+=("$SAVED_PID")
    else
        echo "PID 文件已失效 (${SAVED_PID:-空})，继续查找当前项目真实进程..."
    fi
fi

if [ "${#TARGET_PIDS[@]}" -eq 0 ]; then
    while IFS= read -r FOUND_PID; do
        [ -n "$FOUND_PID" ] && TARGET_PIDS+=("$FOUND_PID")
    done < <(find_project_backends)
fi

rm -f "$PID_FILE"

if [ "${#TARGET_PIDS[@]}" -eq 0 ]; then
    echo "未发现当前项目正在运行的后端进程"
    exit 0
fi

DESCENDANT_PIDS=()
for PID in "${TARGET_PIDS[@]}"; do
    while IFS= read -r CHILD_PID; do
        [ -n "$CHILD_PID" ] && DESCENDANT_PIDS+=("$CHILD_PID")
    done < <(collect_descendants "$PID")
    echo "正在停止当前项目后端进程 (PID: $PID)..."
    kill "$PID" 2>/dev/null || true
done

sleep 2

# 后端正常退出时会先清理模型子进程。这里只处理仍存活的后代，
# 不再使用 pkill 误杀服务器上的其他 LLaMA-Factory 任务。
for CHILD_PID in "${DESCENDANT_PIDS[@]}"; do
    if kill -0 "$CHILD_PID" 2>/dev/null; then
        echo "停止残留子进程 (PID: $CHILD_PID)..."
        kill "$CHILD_PID" 2>/dev/null || true
    fi
done
sleep 1

for PID in "${TARGET_PIDS[@]}" "${DESCENDANT_PIDS[@]}"; do
    if kill -0 "$PID" 2>/dev/null; then
        echo "强制终止残留进程 (PID: $PID)..."
        kill -9 "$PID" 2>/dev/null || true
    fi
done

echo "当前项目已停止"
