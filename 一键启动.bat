@echo off
chcp 65001 >nul
title 王者剪辑 - 环境检测与启动

echo 正在检查运行环境...
python -c "import easyocr; import cv2; import tkinterdnd2" >nul 2>nul
if %errorlevel% neq 0 (
    echo [首次运行] 未检测到完整的运行库，正在自动安装...
    pip install -r requirements.txt
    echo 正在为您下载显卡加速库 (这可能需要几分钟，请耐心等待)...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    echo 环境安装完成！
)

echo 正在启动全自动剪辑界面...
start pythonw gui.py
exit
