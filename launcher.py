import os
import subprocess
import ctypes
import sys

def msg_box(title, text, style):
    # styles: 0=OK, 1=OKCancel, 0x40=Information, 0x10=Stop
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

def check_env():
    # 1. 检查 Python 是否在环境变量中
    try:
        subprocess.run(["python", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        msg_box("错误", "启动失败！未能找到 Python 环境。\n\n请确认您已安装 Python 3，并在安装时勾选了底部的 [Add python.exe to PATH]。", 0x10)
        sys.exit(1)
        
    # 2. 检查必要的第三方库是否已安装
    res = subprocess.run(["python", "-c", "import easyocr; import customtkinter"], capture_output=True)
    if res.returncode != 0:
        ans = msg_box(
            "首次环境初始化", 
            "欢迎使用 王者剪辑 (Modern)！\n\n首次运行未检测到完整的 AI 剪辑运行环境。\n点击【确定】将全自动下载并配置环境（包括数GB的显卡加速库，需大概 2~5 分钟，期间会弹出下载黑框）。\n\n安装完成后，软件剪辑界面将会自动启动！", 
            1 | 0x40  # OKCancel + Information Icon
        )
        if ans != 1: # 1 is IDOK
            sys.exit(0)
            
        # 弹出命令行窗口进行 pip 安装
        os.system("python -m pip install -r requirements.txt")
        os.system("python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")

def main():
    # 确保运行路径正确
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        os.chdir(script_dir)
    except Exception:
        pass
        
    check_env()
    
    # 启动 GUI (隐式使用 pythonw 无命令行黑框)
    subprocess.Popen("start pythonw gui.py", shell=True)

if __name__ == '__main__':
    main()
