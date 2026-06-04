#!/bin/bash
# 剧本杀游戏启动脚本

echo "========================================"
echo "  剧本杀游戏 - 启动脚本"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[1/2] 启动后端服务（自动探测端口）..."
(cd backend && python -m app.main) &
BACKEND_PID=$!

echo "[2/2] 启动前端服务 (http://localhost:5173)..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "服务已启动:"
echo "  - 后端: 见 backend/.port.json 中的端口"
echo "  - 前端: http://localhost:5173（如被占用会自动递增）"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待任意一个进程退出
wait
