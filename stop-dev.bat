@echo off
chcp 65001 >nul
title StudyFlow Agent - Stop

echo 正在停止前后端服务...

:: 停止占用 8000 / 5173 端口的进程
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000.*LISTENING"') do taskkill /PID %%p /F >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173.*LISTENING"') do taskkill /PID %%p /F >nul 2>&1

echo 已停止。
timeout /t 2 >nul
