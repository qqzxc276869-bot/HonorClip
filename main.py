"""
main.py
~~~~~~~
王者荣耀击杀片段自动剪辑工具 - 命令行入口

使用示例：
  python main.py video.mp4
  python main.py video.mp4 --before 10 --after 1 --debug
  python main.py video.mp4 --roi-x 1700 --roi-y 18 --roi-w 60 --roi-h 45

作者：Antigravity / 2026-03-20
"""

import argparse
import sys
from pathlib import Path

from kill_detector import detect_kills
from clip_exporter import export_clips


BANNER = r"""
  ___  __ ___     _   ___ _    ___ ___ ___ ___ ___ 
 | _ \/ /| _ \___| |_/ __| |  |_ _| _ \ _ | __| _ \
 |   / _ \  _/ -_)  _| (__| |__ | ||  _/  _| _||   /
 |_|_\___/_| \___|\__|\___|____|___|_| |_| |___|_|_\ 
  王者荣耀  击杀片段自动剪辑                v1.0
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="王者荣耀击杀片段自动识别与剪辑工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本使用（默认参数）
  python main.py game_video.mp4

  # 自定义剪辑前后时长
  python main.py game_video.mp4 --before 10 --after 1

  # 开启调试模式查看 ROI 是否对准
  python main.py game_video.mp4 --debug --sample-rate 2

  # 自定义 ROI 坐标（当分辨率不是 1080p 时需要调整）
  python main.py game_video.mp4 --roi-x 1700 --roi-y 18 --roi-w 60 --roi-h 45
        """
    )

    # 必填
    parser.add_argument("video", help="输入视频文件路径")

    # 剪辑参数
    parser.add_argument(
        "--output-dir", "-o",
        default=r"E:\素材\片段",
        help="输出目录（默认：./output）"
    )
    parser.add_argument(
        "--before", "-b",
        type=float, default=10.0,
        help="击杀前保留秒数（默认：10）"
    )
    parser.add_argument(
        "--after", "-a",
        type=float, default=1.0,
        help="击杀后保留秒数（默认：1）"
    )

    # 检测参数
    parser.add_argument(
        "--sample-rate", "-s",
        type=int, default=5,
        help="每秒 OCR 采样帧数（默认：5，越高越慢但更准确）"
    )
    parser.add_argument(
        "--cooldown", "-c",
        type=float, default=2.0,
        help="击杀冷却秒数，防止同一击杀被多次计数（默认：2）"
    )

    # ROI 坐标（默认适配 1920×1080 手机投屏）
    parser.add_argument("--roi-x", type=int, default=1700, help="ROI 左上角 X（默认：2040）")
    parser.add_argument("--roi-y", type=int, default=18,   help="ROI 左上角 Y（默认：174）")
    parser.add_argument("--roi-w", type=int, default=60,   help="ROI 宽度（默认：75）")
    parser.add_argument("--roi-h", type=int, default=45,   help="ROI 高度（默认：36）")

    # 调试
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="开启调试窗口，实时显示 ROI 识别结果（按 Q 退出）"
    )

    return parser.parse_args()


def main():
    print(BANNER)
    args = parse_args()

    video_path = args.video
    if not Path(video_path).exists():
        print(f"[错误] 视频文件不存在：{video_path}")
        sys.exit(1)

    roi = (args.roi_x, args.roi_y, args.roi_w, args.roi_h)

    print(f"[配置] 视频文件  : {video_path}")
    print(f"[配置] 输出目录  : {args.output_dir}")
    print(f"[配置] 剪辑区间  : 击杀前 {args.before}s + 击杀后 {args.after}s")
    print(f"[配置] ROI 坐标  : x={roi[0]} y={roi[1]} w={roi[2]} h={roi[3]}")
    print(f"[配置] 采样频率  : {args.sample_rate} 帧/秒")
    print(f"[配置] 冷却时间  : {args.cooldown}s")
    print(f"[配置] 调试模式  : {'开启' if args.debug else '关闭'}")
    print("=" * 60)

    # ── Step 1: 检测击杀时间点 ──────────────────────────────────────
    kill_timestamps = detect_kills(
        video_path=video_path,
        roi=roi,
        sample_rate=args.sample_rate,
        cooldown=args.cooldown,
        debug=args.debug,
    )

    if not kill_timestamps:
        print("\n[结果] 未检测到任何击杀事件。")
        print("  提示：")
        print("  1. 运行 --debug 模式确认 ROI 是否对准击杀数字")
        print("  2. 尝试调整 --roi-x --roi-y --roi-w --roi-h 参数")
        print("  3. 如果数字识别有误，尝试提高 --sample-rate")
        sys.exit(0)

    print(f"\n[结果] 检测到 {len(kill_timestamps)} 次击杀：")
    for i, ts in enumerate(kill_timestamps, 1):
        m, s = divmod(ts, 60)
        print(f"  {i:3d}. {int(m):02d}:{s:05.2f}")

    # ── Step 2: 导出视频片段 ──────────────────────────────────────
    output_files = export_clips(
        video_path=video_path,
        kill_timestamps=kill_timestamps,
        output_dir=args.output_dir,
        before=args.before,
        after=args.after,
    )

    print("\n" + "=" * 60)
    if output_files:
        print(f"🎬 全部完成！共导出 {len(output_files)} 个击杀片段")
        print(f"   输出目录：{Path(args.output_dir).resolve()}")
    else:
        print("❌ 导出失败，请检查 FFmpeg 是否已安装并添加到 PATH")


if __name__ == "__main__":
    main()
