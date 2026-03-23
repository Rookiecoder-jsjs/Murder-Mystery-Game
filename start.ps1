# 剧本杀游戏启动脚本
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  剧本杀游戏 - 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查并安装依赖
if (-not $SkipInstall) {
    Write-Host "[*] 检查依赖..." -ForegroundColor Yellow

    # 安装前端依赖
    if (Test-Path "frontend\node_modules") {
        Write-Host "    [OK] 前端依赖已安装" -ForegroundColor Green
    } else {
        Write-Host "    [安装中] 前端依赖..." -ForegroundColor Yellow
        Push-Location frontend
        npm install
        Pop-Location
    }

    # 检查Python依赖
    Write-Host "    [提示] 确保已安装后端依赖: pip install -r backend/requirements.txt" -ForegroundColor Cyan
}

# 启动后端
Write-Host ""
Write-Host "[1/2] 启动后端服务 (http://localhost:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\backend'; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000" -WindowStyle Normal

Start-Sleep -Seconds 2

# 启动前端
Write-Host "[2/2] 启动前端服务 (http://localhost:5173)..." -ForegroundColor Yellow
Push-Location frontend
npm run dev
Pop-Location
