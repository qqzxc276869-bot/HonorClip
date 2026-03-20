"""
kill_detector.py
~~~~~~~~~~~~~~~~
王者荣耀击杀检测核心模块

逻辑：
  1. 按采样间隔读取视频帧
  2. 裁剪右上角击杀数字区域 (ROI)
  3. 图像预处理 → EasyOCR 识别数字
  4. 当数字增大时记录为一次击杀事件，返回时间点列表

作者：Antigravity / 2026-03-20
"""

import re
import logging
import cv2
import numpy as np
from pathlib import Path

# 静默 EasyOCR / PyTorch 的冗余日志和警告
logging.getLogger("easyocr").setLevel(logging.ERROR)
import warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*")

try:
    import easyocr
except ImportError:
    raise ImportError(
        "请先安装 EasyOCR：pip install easyocr"
    )


# --------------------------------------------------------------------------- #
#  图像预处理
# --------------------------------------------------------------------------- #

def _preprocess_roi(roi: np.ndarray) -> np.ndarray:
    """
    对裁剪出的 ROI 进行预处理，提升 EasyOCR 准确率。
    EasyOCR 对自然图像识别较好，此处仅放大并增强对比度，不使用导致图像破损的强力二值化。
    """
    # 放大 3x，改善 OCR 对小字体的识别
    roi = cv2.resize(roi, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 转灰度
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # CLAHE 对比度增强
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    
    # 转回 3 通道（EasyOCR 可通过 allowlist 辅助识别，RGB/GRAY 均可）
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


# --------------------------------------------------------------------------- #
#  数字解析
# --------------------------------------------------------------------------- #

def _parse_number(ocr_result) -> int | None:
    """
    从 EasyOCR 结果中提取第一个整数。
    EasyOCR 返回格式：[(bbox, text, confidence), ...]
    返回 None 表示未识别到数字。
    """
    if not ocr_result:
        return None
    for (_, text, confidence) in ocr_result:
        if confidence < 0.25:
            continue
        match = re.search(r'\d+', text)
        if match:
            return int(match.group())
    return None


# --------------------------------------------------------------------------- #
#  主检测函数
# --------------------------------------------------------------------------- #

def detect_kills(
    video_path: str,
    roi: tuple[int, int, int, int] = (1700, 18, 60, 45),
    sample_rate: int = 5,
    cooldown: float = 2.0,
    debug: bool = False,
    output_dir: str = "",
) -> list[float]:
    """
    从视频中检测击杀事件，返回每次击杀发生的时间戳列表（单位：秒）。

    Parameters
    ----------
    video_path : str
        输入视频文件路径
    roi : (x, y, w, h)
        击杀数字在视频帧中的像素位置（默认适配 1920×1080 手机投屏）
    sample_rate : int
        每秒采样帧数（越高越准，速度越慢）
    cooldown : float
        同一击杀事件的冷却秒数，防止数字抖动导致重复计数
    debug : bool
        开启后实时显示 ROI 预览窗口（按 Q 退出）

    Returns
    -------
    list[float]
        击杀时间戳列表，单位秒
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"无法打开视频文件：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    frame_interval = max(1, int(fps / sample_rate))

    print(f"[检测] 视频：{video_path}")
    print(f"[检测] FPS={fps:.1f}  总帧数={total_frames}  时长={duration:.1f}s")
    print(f"[检测] ROI={roi}  采样间隔={frame_interval}帧  冷却={cooldown}s")
    print("-" * 60)

    # 初始化 EasyOCR（使用 GPU，大幅提升速度）
    ocr = easyocr.Reader(['ch_sim', 'en'], gpu=True, verbose=False)

    x, y, w, h = roi
    kill_timestamps: list[float] = []
    last_kill_num: int = -1             # 初始化为 -1，表示还未确认任何初始击杀数
    last_kill_ts: float = -cooldown
    prev_roi_gray: np.ndarray | None = None
    frames_since_change: int = 999
    num_history: list[int] = []         # 最近几次 OCR 识别到的数字
    ocr_calls = 0
    sampled = 0
    frame_idx = 0

    while frame_idx < total_frames:
        # ── 直接 seek 到目标帧，跳过中间所有帧的解码 ──────────────
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        sampled += 1
        timestamp = frame_idx / fps

        # 裁剪 ROI（防止越界）
        fh, fw = frame.shape[:2]
        x1 = min(x, fw - 1)
        y1 = min(y, fh - 1)
        x2 = min(x + w, fw)
        y2 = min(y + h, fh)
        roi_img = frame[y1:y2, x1:x2]

        if roi_img.size > 0:
            # ── 帧差检测：画面变化后，连续 5 个采样帧都执行 OCR（等待击杀动画落座） ──
            roi_gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            if prev_roi_gray is not None and prev_roi_gray.shape == roi_gray.shape:
                diff = cv2.absdiff(roi_gray, prev_roi_gray)
                changed_ratio = np.count_nonzero(diff > 30) / diff.size
                if changed_ratio > 0.02:      # 变化像素 > 2%，说明发生变化
                    frames_since_change = 0
            else:
                frames_since_change = 0       # 第一帧强制 OCR

            prev_roi_gray = roi_gray

            run_ocr = (frames_since_change <= 5)
            frames_since_change += 1

            current_num = None
            processed = None
            if run_ocr:
                processed = _preprocess_roi(roi_img)
                result = ocr.readtext(processed, allowlist='0123456789')
                current_num = _parse_number(result)
                ocr_calls += 1

                # 记录识别历史以消除单帧抖动
                if current_num is not None:
                    num_history.append(current_num)
                    if len(num_history) > 3:
                        num_history.pop(0)

            # ---------- 判定稳定数字 ----------
            # 当最近两次识别到的数字完全一样时，我们才认为它是一个“稳定”的真实数字
            stable_num = None
            if len(num_history) >= 2 and num_history[-1] == num_history[-2]:
                stable_num = num_history[-1]

            # ---------- 击杀判断 ----------
            if stable_num is not None:
                if last_kill_num == -1:
                    last_kill_num = stable_num  # 第一次获得稳定数字，作为基准，不触发击杀

                elif stable_num > last_kill_num:
                    kill_amount = stable_num - last_kill_num
                    
                    # 防抖过滤：一次击杀最多涨 5 个。如果是跳剪导致的突增，不在此处记录高光。
                    if kill_amount <= 5:
                        if timestamp - last_kill_ts >= cooldown:
                            kill_timestamps.append(timestamp)
                            last_kill_ts = timestamp
                            print(
                                f"  ✅ 击杀！时间={timestamp:.2f}s  "
                                f"KD: {last_kill_num} → {stable_num}  "
                                f"(+{kill_amount})"
                            )
                            
                            # ── 保存调试截图，排查“误报” ──
                            if output_dir:
                                dbg_dir = Path(output_dir) / ".debug_kills"
                                dbg_dir.mkdir(parents=True, exist_ok=True)
                                base_name = f"t_{timestamp:.1f}s_read_{stable_num}"
                                dbg_frame = frame.copy()
                                cv2.rectangle(dbg_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.imwrite(str(dbg_dir / f"{base_name}_frame.jpg"), dbg_frame)
                                cv2.imwrite(str(dbg_dir / f"{base_name}_roi.jpg"), roi_img)

                    # 只要稳定数字增加了，都更新基准
                    last_kill_num = stable_num

                elif stable_num < last_kill_num:
                    # 稳定数字发生了【极小化下降】，只可能是新开了一局游戏，或者是之前的基准被连错毒化。信任并重置！
                    last_kill_num = stable_num

            # ---------- 调试窗口 ----------
            if debug:
                debug_frame = frame.copy()
                cv2.rectangle(debug_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                num_text = str(current_num) if current_num is not None else "-"
                cv2.putText(
                    debug_frame,
                    f"Kill={num_text}  t={timestamp:.1f}s",
                    (x1, max(y1 - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )
                if processed is not None:
                    roi_show = cv2.resize(processed, (processed.shape[1] // 2, processed.shape[0] // 2))
                    debug_frame[0:roi_show.shape[0], 0:roi_show.shape[1]] = roi_show
                cv2.imshow("Kill Detector - Debug (Press Q to quit)", debug_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("[DEBUG] 用户按下 Q，提前结束检测。")
                    break

        # 进度显示
        if sampled % 200 == 0:
            progress = frame_idx / total_frames * 100
            print(f"  ⏳ 进度 {progress:.1f}%  采样={sampled}  OCR={ocr_calls}次", end='\r')

        frame_idx += frame_interval   # 直接跳到下一个采样点

    cap.release()
    if debug:
        cv2.destroyAllWindows()

    print(f"\n[检测] 完成！共采样 {sampled} 帧，实际 OCR {ocr_calls} 次")
    print(f"[检测] 共发现 {len(kill_timestamps)} 次击杀")
    return kill_timestamps
