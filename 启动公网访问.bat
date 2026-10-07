@echo off
chcp 65001 >nul
title 智面 AI - 公网版
cd /d "%~dp0"

set TF_ENV=E:\anaconda3\envs\tf_env\python.exe
set PROJ_DIR=%~dp0
set CF=C:\Users\OSCORP\tools\cloudflared.exe

if not exist "%TF_ENV%" (
    echo [错误] 找不到 Python: %TF_ENV%
    pause
    exit /b 1
)
if not exist "%CF%" (
    echo [错误] 找不到 cloudflared: %CF%
    pause
    exit /b 1
)

echo ========================================================
echo   智面 AI - 公网访问模式 (Cloudflare Tunnel)
echo ========================================================
echo.
echo [1/3] 启动本地服务...
set CUDA_VISIBLE_DEVICES=
start "AI问答本地服务" /min "%TF_ENV%" "%PROJ_DIR%ai智能问答.py"

echo [2/3] 等待服务就绪 (约8秒)...
timeout /t 8 /nobreak >nul

echo [3/3] 启动 Cloudflare 隧道...
echo.
echo ========================================================
echo   隧道正在连接...
echo   看到 "https://xxxx-xxxx.trycloudflare.com" 就是你的公网地址！
echo   把这个地址发给任何人，他们浏览器打开就能用。
echo   关闭此窗口 = 停止公网访问
echo ========================================================
echo.

"%CF%" tunnel --url http://127.0.0.1:5000 --no-autoupdate --protocol http2
pause