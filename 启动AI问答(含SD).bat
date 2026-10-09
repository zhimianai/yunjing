@echo off
chcp 65001 >nul
title 云镜 AI - 本地版 (含 Stable Diffusion)
echo ============================================
echo   云镜 AI 智能问答系统 - 本地版
echo   带 Stable Diffusion + LoRA 图片生成
echo ============================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [1/3] 检查 PyTorch...
python -c "import torch; print(f'  PyTorch {torch.__version__}  CUDA={torch.cuda.is_available()}')" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 PyTorch CUDA 版...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
)

echo.
echo [2/3] 检查 diffusers...
python -c "import diffusers; print(f'  diffusers {diffusers.__version__}')" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 diffusers...
    pip install diffusers transformers accelerate safetensors Pillow
)

echo.
echo [3/3] 启动 Flask 服务器...
echo.
echo --------------------------------------------
echo   本地访问: http://127.0.0.1:5000
echo --------------------------------------------
echo.
echo 提示: 首次生成图片会下载 SD 1.5 模型(约4GB)
echo       请耐心等待，后续会使用缓存
echo.

python app_factory.py

pause
