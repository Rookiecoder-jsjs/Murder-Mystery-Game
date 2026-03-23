@echo off
echo ========================================
echo   剧本杀游戏 - 启动中
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 启动后端服务 (端口 8000)...
start "Backend" cmd /k "cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] 启动前端服务 (端口 5173)...
cd frontend
call npm run dev

cd ..
