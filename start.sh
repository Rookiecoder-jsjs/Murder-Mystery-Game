#!/bin/bash
# 剧本杀游戏启动脚本

echo "========================================"
echo "  剧本杀游戏 - 启动脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/2] 启动后端服务 (http://localhost:8000)..."
(cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

echo "[2/2] 启动前端服务 (http://localhost:5173)..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "服务已启动:"
echo "  - 后端: http://localhost:8000"
echo "  - 前端: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待任意一个进程退出
wait
