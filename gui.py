"""
gui.py
~~~~~~
王者荣耀击杀片段自动剪辑工具 - 图形界面入口

拖入视频文件，点击"开始剪辑"即可自动识别并导出击杀片段。
依赖：tkinterdnd2（pip install tkinterdnd2）
"""

import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2

# 尝试导入 tkinterdnd2（支持拖拽）
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

from kill_detector import detect_kills
from clip_exporter import export_clips


# ── 配色 ──────────────────────────────────────────────
BG        = "#1a1a2e"
BG2       = "#16213e"
ACCENT    = "#e94560"
ACCENT2   = "#0f3460"
FG        = "#e0e0e0"
FG_DIM    = "#888"
BTN_FG    = "#ffffff"
CARD      = "#0f3460"
SEP       = "#2a2a4a"
GREEN     = "#4ecca3"
FONT      = ("Segoe UI", 10)
FONT_B    = ("Segoe UI", 10, "bold")
FONT_T    = ("Segoe UI", 18, "bold")
FONT_SM   = ("Segoe UI", 9)


class KillClipperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("王者剪辑  v1.0")
        self.root.configure(bg=BG)
        self.root.geometry("620x700")
        self.root.resizable(False, False)

        self.video_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=r"E:\素材\片段")
        self.before     = tk.DoubleVar(value=10.0)
        self.after      = tk.DoubleVar(value=1.0)
        self.sample     = tk.IntVar(value=5)
        self.cooldown   = tk.DoubleVar(value=2.0)
        self.roi_x      = tk.IntVar(value=1700)
        self.roi_y      = tk.IntVar(value=18)
        self.roi_w      = tk.IntVar(value=60)
        self.roi_h      = tk.IntVar(value=45)
        self.debug_mode = tk.BooleanVar(value=False)

        self._build_ui()

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self):
        # 标题栏
        title_frame = tk.Frame(self.root, bg=ACCENT2, pady=12)
        title_frame.pack(fill="x")
        tk.Label(title_frame, text="⚔  王者剪辑", font=FONT_T,
                 bg=ACCENT2, fg=ACCENT).pack()
        tk.Label(title_frame, text="击杀片段自动识别 & 剪辑工具",
                 font=FONT_SM, bg=ACCENT2, fg=FG_DIM).pack()

        content = tk.Frame(self.root, bg=BG, padx=20, pady=10)
        content.pack(fill="both", expand=True)

        # 视频拖放区
        self._build_drop_zone(content)

        # 参数设置
        self._build_params(content)

        # 调试勾选
        dbg_row = tk.Frame(content, bg=BG)
        dbg_row.pack(fill="x", pady=(4, 0))
        tk.Checkbutton(dbg_row, text="调试模式（实时显示 ROI 识别结果，按 Q 退出）",
                       variable=self.debug_mode, bg=BG, fg=FG_DIM,
                       selectcolor=BG2, activebackground=BG,
                       font=FONT_SM).pack(side="left")

        # 开始按钮
        self.btn_run = tk.Button(
            content, text="▶  开始剪辑",
            font=("Segoe UI", 12, "bold"),
            bg=ACCENT, fg=BTN_FG,
            activebackground="#cc3350", activeforeground=BTN_FG,
            relief="flat", cursor="hand2",
            pady=10, borderwidth=0,
            command=self._on_run
        )
        self.btn_run.pack(fill="x", pady=(14, 4))
        self._add_hover(self.btn_run, ACCENT, "#cc3350")

        # 进度 / 日志区
        self._build_log(content)

    def _build_drop_zone(self, parent):
        zone_frame = tk.Frame(parent, bg=BG)
        zone_frame.pack(fill="x", pady=(8, 4))

        self.drop_label = tk.Label(
            zone_frame,
            text="🎬  将视频文件拖到此处\n或点击选择文件",
            font=("Segoe UI", 11),
            bg=BG2, fg=FG_DIM,
            relief="flat",
            pady=28, padx=20,
            cursor="hand2",
        )
        self.drop_label.pack(fill="x")
        self.drop_label.bind("<Button-1>", lambda e: self._browse_video())

        # 绑定拖拽
        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self.drop_label.config(text="🎬  点击选择视频文件\n（安装 tkinterdnd2 可支持拖拽）")

        # 已选文件显示
        self.file_label = tk.Label(
            zone_frame, textvariable=self.video_path,
            font=FONT_SM, bg=BG, fg=GREEN,
            wraplength=570, justify="left"
        )
        self.file_label.pack(anchor="w", pady=(4, 0))

    def _build_params(self, parent):
        card = tk.LabelFrame(parent, text=" 参数设置 ", font=FONT_SM,
                             bg=BG, fg=FG_DIM, bd=1, relief="groove",
                             padx=10, pady=8)
        card.pack(fill="x", pady=8)

        rows = [
            ("输出目录",   self.output_dir, "entry", "str"),
            ("击杀前 (秒)", self.before,     "spin",  {"from_": 1, "to": 60,  "increment": 0.5}),
            ("击杀后 (秒)", self.after,      "spin",  {"from_": 0, "to": 30,  "increment": 0.5}),
            ("采样帧率/秒", self.sample,     "spin",  {"from_": 1, "to": 30,  "increment": 1}),
            ("冷却时间 (秒)",self.cooldown,  "spin",  {"from_": 0.5, "to": 10,"increment": 0.5}),
        ]
        for label_text, var, wtype, opts in rows:
            row = tk.Frame(card, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label_text, width=12, anchor="w",
                     font=FONT, bg=BG, fg=FG).pack(side="left")
            if wtype == "entry":
                w = tk.Entry(row, textvariable=var, bg=BG2, fg=FG,
                             insertbackground=FG, relief="flat", font=FONT,
                             width=40)
                if label_text == "输出目录":
                    w.pack(side="left", fill="x", expand=True)
                    tk.Button(row, text="…", bg=ACCENT2, fg=FG, relief="flat",
                              cursor="hand2", font=FONT,
                              command=self._browse_output).pack(side="left", padx=(4,0))
                else:
                    w.pack(side="left", fill="x", expand=True)
            else:  # spinbox
                w = tk.Spinbox(row, textvariable=var,
                               bg=BG2, fg=FG, buttonbackground=ACCENT2,
                               relief="flat", font=FONT, width=8,
                               **opts)
                w.pack(side="left")

        # ROI（折叠式）
        self._build_roi(card)

    def _build_roi(self, parent):
        roi_frame = tk.Frame(parent, bg=BG)
        roi_frame.pack(fill="x", pady=(4, 0))
        self._roi_visible = False

        hdr = tk.Frame(roi_frame, bg=BG)
        hdr.pack(fill="x")
        self._roi_toggle_btn = tk.Button(
            hdr, text="▶ 高级：ROI 坐标（非 1080p 时调整）",
            font=FONT_SM, bg=BG, fg=FG_DIM,
            relief="flat", cursor="hand2", anchor="w",
        )
        self._roi_toggle_btn.pack(side="left", fill="x", expand=True)
        self._roi_toggle_btn.config(
            command=lambda: self._toggle_roi(self._roi_toggle_btn, roi_detail)
        )

        # 校准按钮
        calib_btn = tk.Button(
            hdr, text="🎯 可视化校准",
            font=FONT_SM, bg=ACCENT2, fg=FG,
            relief="flat", cursor="hand2", padx=6,
            command=self._calibrate_roi
        )
        calib_btn.pack(side="right")
        self._add_hover(calib_btn, ACCENT2, "#1a4a80")

        roi_detail = tk.Frame(roi_frame, bg=BG)
        roi_cfg = [
            ("ROI X", self.roi_x), ("ROI Y", self.roi_y),
            ("ROI W", self.roi_w), ("ROI H", self.roi_h),
        ]
        row = tk.Frame(roi_detail, bg=BG)
        row.pack(anchor="w")
        for lbl, var in roi_cfg:
            tk.Label(row, text=lbl, font=FONT_SM, bg=BG, fg=FG_DIM).pack(side="left", padx=(0,2))
            tk.Spinbox(row, textvariable=var, from_=0, to=9999, increment=1,
                       bg=BG2, fg=FG, buttonbackground=ACCENT2,
                       relief="flat", font=FONT_SM, width=6).pack(side="left", padx=(0, 10))

    def _toggle_roi(self, btn, frame):
        if self._roi_visible:
            frame.pack_forget()
            btn.config(text="▶ 高级：ROI 坐标（非 1080p 时调整）")
        else:
            frame.pack(fill="x")
            btn.config(text="▼ 高级：ROI 坐标（非 1080p 时调整）")
        self._roi_visible = not self._roi_visible

    def _calibrate_roi(self):
        """打开视频中间帧，让用户用鼠标框选击杀数字区域，自动填入 ROI 坐标。"""
        vp = self.video_path.get().strip()
        if not vp:
            messagebox.showwarning("提示", "请先选择视频文件！")
            return
        if not Path(vp).exists():
            messagebox.showerror("错误", f"视频文件不存在：\n{vp}")
            return

        def _do_calibrate():
            cap = cv2.VideoCapture(vp)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # 跳到视频 1/4 处（一般已开始游戏）
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 4))
            ret, frame = cap.read()
            cap.release()
            if not ret:
                self.root.after(0, lambda: messagebox.showerror("错误", "无法读取视频帧"))
                return

            # 缩放到最大 1280 宽（大屏幕友好）
            h, w = frame.shape[:2]
            scale = min(1.0, 1280 / w)
            disp = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame.copy()

            cv2.putText(disp,
                "[校准] 用鼠标拖拽框选击杀数字  ->  按 SPACE/ENTER 确认  |  按 C 取消",
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 100), 2)

            roi_sel = cv2.selectROI(
                "ROI 校准（框选击杀数字后按 Enter）",
                disp, showCrosshair=True, fromCenter=False
            )
            cv2.destroyAllWindows()

            rx, ry, rw, rh = roi_sel
            if rw == 0 or rh == 0:
                return   # 用户取消

            # 还原为原始分辨率坐标
            rx = int(rx / scale)
            ry = int(ry / scale)
            rw = int(rw / scale)
            rh = int(rh / scale)

            def _apply():
                self.roi_x.set(rx)
                self.roi_y.set(ry)
                self.roi_w.set(rw)
                self.roi_h.set(rh)
                # 自动展开 ROI 面板
                if not self._roi_visible:
                    self._roi_toggle_btn.invoke()
                self._log(f"✅ ROI 已更新：x={rx} y={ry} w={rw} h={rh}\n")
            self.root.after(0, _apply)

        threading.Thread(target=_do_calibrate, daemon=True).start()

    def _build_log(self, parent):
        tk.Label(parent, text="运行日志", font=FONT_SM,
                 bg=BG, fg=FG_DIM, anchor="w").pack(fill="x", pady=(4, 0))
        log_frame = tk.Frame(parent, bg=BG2, relief="flat")
        log_frame.pack(fill="both", expand=True, pady=(2, 8))

        self.log_text = tk.Text(
            log_frame, bg=BG2, fg=FG, font=("Consolas", 9),
            wrap="word", relief="flat", state="disabled",
            height=10, insertbackground=FG
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ── 交互逻辑 ────────────────────────────────────────

    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mov *.avi *.mkv *.flv"), ("所有文件", "*.*")]
        )
        if path:
            self._set_video(path)

    def _browse_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir.set(d)

    def _on_drop(self, event):
        # tkinterdnd2 返回的路径可能带花括号
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        self._set_video(raw)

    def _set_video(self, path: str):
        self.video_path.set(path)
        self.drop_label.config(
            text=f"✅  {Path(path).name}",
            fg=GREEN, font=FONT_B
        )
        self._log(f"已选择视频：{path}\n")

    def _on_run(self):
        vp = self.video_path.get().strip()
        if not vp:
            messagebox.showwarning("提示", "请先选择视频文件！")
            return
        if not Path(vp).exists():
            messagebox.showerror("错误", f"视频文件不存在：\n{vp}")
            return

        self.btn_run.config(state="disabled", text="⏳  正在处理…")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        vp   = self.video_path.get().strip()
        odir = self.output_dir.get().strip()
        roi  = (self.roi_x.get(), self.roi_y.get(),
                self.roi_w.get(), self.roi_h.get())

        self._log("=" * 50 + "\n")
        self._log(f"▶ 开始处理：{Path(vp).name}\n")
        self._log(f"  输出目录：{odir}\n")
        self._log(f"  击杀前后：{self.before.get()}s / {self.after.get()}s\n")
        self._log(f"  ROI：{roi}\n")
        self._log("=" * 50 + "\n")

        try:
            # Step 1: 检测击杀
            self._log("\n[1/2] 正在检测击杀时间点…\n")
            timestamps = detect_kills(
                video_path=vp,
                roi=roi,
                sample_rate=self.sample.get(),
                cooldown=self.cooldown.get(),
                debug=self.debug_mode.get(),
                output_dir=odir,
            )

            if not timestamps:
                self._log("\n⚠  未检测到任何击杀事件。\n")
                self._log("  提示：开启调试模式确认 ROI 是否对准击杀数字。\n")
                self._finish_ui()
                return

            self._log(f"\n✅  检测到 {len(timestamps)} 次击杀：\n")
            for i, ts in enumerate(timestamps, 1):
                m, s = divmod(ts, 60)
                self._log(f"   {i:3d}. {int(m):02d}:{s:05.2f}\n")

            # Step 2: 导出片段
            self._log(f"\n[2/2] 正在导出 {len(timestamps)} 个视频片段…\n")
            out_files = export_clips(
                video_path=vp,
                kill_timestamps=timestamps,
                output_dir=odir,
                before=self.before.get(),
                after=self.after.get(),
            )

            if out_files:
                self._log(f"\n🎬  全部完成！共导出 {len(out_files)} 个片段\n")
                self._log(f"   输出目录：{Path(odir).resolve()}\n")
            else:
                self._log("\n❌  导出失败，请检查 FFmpeg 是否已安装并添加到 PATH。\n")

        except Exception as e:
            self._log(f"\n❌  运行出错：{e}\n")

        self._finish_ui()

    def _finish_ui(self):
        self.root.after(0, lambda: self.btn_run.config(
            state="normal", text="▶  开始剪辑"))

    def _log(self, msg: str):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _append)

    @staticmethod
    def _add_hover(widget, normal_bg, hover_bg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))


# ── 入口 ─────────────────────────────────────────────

def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    # Windows 任务栏图标（可选）
    try:
        root.iconbitmap(default="icon.ico")
    except Exception:
        pass

    app = KillClipperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
