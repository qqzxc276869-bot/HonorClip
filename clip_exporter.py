"""
clip_exporter.py
~~~~~~~~~~~~~~~~
基于击杀时间戳列表，合并重叠片段并调用 FFmpeg 进行无损视频切割。

作者：Antigravity / 2026-03-20
"""

import os
import subprocess
from pathlib import Path


# --------------------------------------------------------------------------- #
#  片段合并
# --------------------------------------------------------------------------- #

def _build_segments(
    kill_timestamps: list[float],
    video_duration: float,
    before: float = 10.0,
    after: float = 1.0,
) -> list[tuple[float, float, list[float]]]:
    """
    根据击杀时间列表生成剪辑区间，自动合并时间上重叠的区间。

    Returns
    -------
    list of (start, end, kill_list)
        start / end 均已 clamp 至 [0, video_duration]
        kill_list 是该片段内涵盖的击杀时间点
    """
    if not kill_timestamps:
        return []

    # 构建原始区间
    intervals: list[tuple[float, float, float]] = []
    for ts in sorted(kill_timestamps):
        seg_start = max(0.0, ts - before)
        seg_end = min(video_duration, ts + after)
        intervals.append((seg_start, seg_end, ts))

    # 合并重叠区间
    merged: list[tuple[float, float, list[float]]] = []
    cur_start, cur_end, cur_kills = intervals[0][0], intervals[0][1], [intervals[0][2]]

    for seg_start, seg_end, ts in intervals[1:]:
        if seg_start <= cur_end:          # 有重叠，直接扩展
            cur_end = max(cur_end, seg_end)
            cur_kills.append(ts)
        else:                             # 无重叠，保存并开始新区间
            merged.append((cur_start, cur_end, cur_kills))
            cur_start, cur_end, cur_kills = seg_start, seg_end, [ts]

    merged.append((cur_start, cur_end, cur_kills))
    return merged


# --------------------------------------------------------------------------- #
#  FFmpeg 切割
# --------------------------------------------------------------------------- #

def _run_ffmpeg(
    input_path: str,
    start: float,
    end: float,
    output_path: str,
) -> bool:
    """
    调用 FFmpeg 进行无损切割（stream copy）。
    返回 True 表示成功。
    """
    duration = end - start
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", input_path,
        "-t", f"{duration:.3f}",
        "-c", "copy",           # 无损复制，速度极快
        "-avoid_negative_ts", "1",
        output_path
    ]
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=300,
            **kwargs
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-500:]
            print(f"  [FFmpeg 错误] {err}")
            return False
        return True
    except FileNotFoundError:
        raise EnvironmentError(
            "未找到 FFmpeg。请安装 FFmpeg 并将其添加到 PATH。\n"
            "下载地址：https://ffmpeg.org/download.html"
        )
    except subprocess.TimeoutExpired:
        print("  [FFmpeg 超时]")
        return False


# --------------------------------------------------------------------------- #
#  主导出函数
# --------------------------------------------------------------------------- #

def export_clips(
    video_path: str,
    kill_timestamps: list[float],
    output_dir: str = "./output",
    before: float = 10.0,
    after: float = 1.0,
) -> list[str]:
    """
    根据击杀时间戳生成视频片段。

    Parameters
    ----------
    video_path : str
        原始视频文件路径
    kill_timestamps : list[float]
        击杀发生的时间戳列表（秒）
    output_dir : str
        片段输出目录
    before : float
        击杀前保留秒数
    after : float
        击杀后保留秒数

    Returns
    -------
    list[str]
        成功生成的输出文件路径列表
    """
    if not kill_timestamps:
        print("[导出] 没有检测到击杀，无需导出。")
        return []

    # 获取视频总时长
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

    probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", video_path
    ]
    try:
        import json
        probe_result = subprocess.run(
            probe_cmd, capture_output=True, timeout=30, **kwargs
        )
        info = json.loads(probe_result.stdout)
        video_duration = float(info["format"]["duration"])
    except Exception:
        # fallback：用 opencv 获取时长
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        video_duration = frames / fps
        cap.release()

    # 构建并合并片段
    segments = _build_segments(kill_timestamps, video_duration, before, after)

    # 准备输出目录
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 获取原始文件名（不含扩展名）
    input_name = Path(video_path).stem
    input_ext = Path(video_path).suffix or ".mp4"

    print(f"\n[导出] 共 {len(segments)} 个片段，输出至：{out_dir.resolve()}")
    print("-" * 60)

    output_files: list[str] = []
    for idx, (start, end, kills) in enumerate(segments, start=1):
        kills_str = "+".join(f"{k:.1f}s" for k in kills)
        filename = f"{input_name}_kill_{idx:03d}_[{kills_str}].mp4"
        # Windows 路径安全：替换非法字符
        filename = filename.replace(":", "-").replace("*", "x")
        out_path = str(out_dir / filename)

        print(
            f"  [{idx}/{len(segments)}] {start:.1f}s → {end:.1f}s  "
            f"(时长 {end-start:.1f}s)  击杀点: {kills_str}"
        )

        success = _run_ffmpeg(video_path, start, end, out_path)
        if success:
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"    ✅ 已保存：{filename}  ({size_mb:.1f} MB)")
            output_files.append(out_path)
        else:
            print(f"    ❌ 导出失败：{filename}")

    print(f"\n[导出] 完成！成功导出 {len(output_files)}/{len(segments)} 个片段")
    return output_files
