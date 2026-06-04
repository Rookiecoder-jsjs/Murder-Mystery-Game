@echo off
echo ========================================
echo   剧本杀游戏 - 启动中
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] 启动后端服务（自动探测端口）...
start "Backend" cmd /k "cd backend && python -m app.main"

echo [2/2] 启动前端服务 (端口 5173)...
cd frontend
call npm run dev

cd ..
