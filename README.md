# ⚔️ HonorClip (王者剪辑)

一款基于 **EasyOCR** 与 **PyTorch** 深度学习驱动的《王者荣耀》高能片段全自动识别与无损剪辑工具。

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ 项目亮点

- **🧠 AI 视觉驱动**：摒弃传统的像素比对，采用 EasyOCR 深度神经网络实时追踪屏幕右上角的数子变化，识别极其稳健。
- **⚡ 显卡硬件加速**：原生支持 CUDA 加速（支持 NVIDIA 系列显卡），扫描 20 分钟的视频仅需 1 分钟左右。
- **🎛️ 现代化 UI 交互**：基于 CustomTkinter 重构的极简黑白 UI，支持深色模式、圆角布局及丝滑的进度反馈。
- **📂 批量化处理**：支持多选视频或文件夹拖拽，一键挂机处理全天的对局录像。
- **🎯 可视化校准**：内置鼠标拖拽校准功能，完美适配各种手机投屏比例（iPad/16:9/21:9 无缝切换）。
- **🚀 零损快剪**：调用 FFmpeg 引擎进行时间戳提取，无需二次压制，导出速度极快且画质丝毫无损。

---

## 📸 界面预览

> [!TIP]
> <img width="1527" height="1166" alt="cd828c73-5778-4911-9c23-fb1ed46baf2a" src="https://github.com/user-attachments/assets/8e449854-a650-4122-b64f-6165231091f8" />

---

## 🛠️ 环境准备

1. **安装 Python**：建议版本 3.8 ~ 3.12。
2. **下载 FFmpeg**：
   - 剪辑功能强依赖 FFmpeg，请确保其已安装并添加到系统环境变量 `PATH` 中。
   - [FFmpeg 官网下载指引](https://ffmpeg.org/download.html)
3. **（推荐）安装 CUDA**：如果你有 NVIDIA 显卡，建议安装 CUDA 12.1 以获得 10 倍速以上的识别提升。

---

## 🚀 快速上手

### 方式 A：开发者模式 (源码运行)
克隆项目后运行以下命令：
```bash
# 自动安装所有依赖与显卡驱动环境
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 启动图形界面
python gui.py
```

### 方式 B：一键启动 (推荐用户)
双击项目根目录下的 **`一键启动.bat`** (或你编译的 `王者剪辑.exe`)，程序会自动检测并初始化环境。

---

## 📖 核心功能指引

1. **导入视频**：将你的游戏录像（支持 MP4 / MOV 等）直接拖入程序中心的灰色框。
2. **设定区间**：
   - `击杀前保留` (10s)：录下击杀前的操作过程。
   - `击杀后延后` (1s)：录下杀完人后那帅气的瞬间。
3. **可视化校准**：
   - 如果你的视频比例比较特殊，点击【🎯 截帧校准】。
   - 在弹出的窗口中用鼠标框选你的“击杀数字”区域并按空格确认，程序会自动学习位置。
4. **开始批量剪辑**：点击大按钮，坐等高能片段产出！

---

## 📂 项目结构

```text
HonorClip/
├── main.py            # 命令行入口 (支持 CLI 操作)
├── gui.py             # 现代化图形界面 (CustomTkinter)
├── kill_detector.py   # OCR 逻辑与击杀判定算法 (Core)
├── clip_exporter.py   # FFmpeg 剪辑调度引擎
├── launcher.py        # EXE 启动器源码
└── requirements.txt   # 依赖列表
```

---

## 📜 声明与贡献

- 本工具仅用于技术交流与个人剪辑效率提升，请勿用于任何侵权或违规商业行为。
- 欢迎提交 Issue 或 Pull Request 来完善识别算法！

---

**如果这个项目帮到了你，请给一个 Star ⭐️ 鼓励一下作者！**
