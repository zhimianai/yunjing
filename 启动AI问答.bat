@echo off
chcp 65001 >nul
title 智面 AI - 本地版
cd /d "%~dp0"

set TF_ENV=E:\anaconda3\envs\tf_env\python.exe
set PROJ_DIR=%~dp0

if not exist "%TF_ENV%" (
    echo [错误] 找不到 Python: %TF_ENV%
    pause
    exit /b 1
)

echo [1/2] 启动服务...
set CUDA_VISIBLE_DEVICES=
start "AI问答服务" /min "%TF_ENV%" "%PROJ_DIR%ai智能问答.py"

echo [2/2] 等待服务就绪...
timeout /t 8 /nobreak >nul

echo [完成] 智面 AI 已在浏览器中打开
start "" "http://zhimian.ai:5000"
exit /b 0