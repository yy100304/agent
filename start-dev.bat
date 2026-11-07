@echo off
chcp 65001 >nul
title StudyFlow Agent - Dev Launcher

echo ============================================
echo   智学 Agent (StudyFlow Agent) 一键启动
echo ============================================
echo.

cd /d "%~dp0"

:: ---- 启动后端 (FastAPI, 端口 8000) ----
echo [1/2] 启动后端 FastAPI (http://127.0.0.1:8000)...
start "StudyFlow-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: ---- 启动前端 (Vite, 端口 5173) ----
echo [2/2] 启动前端 Vite (http://localhost:5173)...
start "StudyFlow-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo 启动完成！两个新窗口分别运行前后端。
echo 浏览器访问: http://localhost:5173
echo 测试账号:   demo / demo123
echo.
echo 关闭服务: 直接关掉两个窗口，或运行 stop-dev.bat
echo.
timeout /t 3 >nul
start http://localhost:5173
