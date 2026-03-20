"""
gui.py
~~~~~~
王者荣耀击杀片段自动剪辑工具 - 图形界面入口
"""

import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
import json

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"

import customtkinter as ctk

# 尝试导入 tkinterdnd2（支持拖拽）
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

from kill_detector import detect_kills
from clip_exporter import export_clips

# ── 配色与主题 (极简黑白) ───────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

GREEN     = "#ffffff"
ACCENT    = "#ffffff"
FONT      = ("Segoe UI", 13)
FONT_B    = ("Segoe UI", 13, "bold")
FONT_SM   = ("Segoe UI", 12)


if HAS_DND:
    class CTk_TkinterDnD(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    CTk_TkinterDnD = ctk.CTk


class NumInput(ctk.CTkFrame):
    """自定义数字步进增减组件"""
    def __init__(self, master, var, from_, to, increment, width=120, **kwargs):
        super().__init__(master, width=width, height=32, corner_radius=6, **kwargs)
        self.var = var
        self.min_v = from_
        self.max_v = to
        self.inc = increment

        btn_w = 28
        self.btn_sub = ctk.CTkButton(self, text="-", width=btn_w, height=32, fg_color="transparent", 
                                     hover_color=("gray70", "gray30"), command=self._sub)
        self.btn_sub.pack(side="left", padx=(2, 0))

        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=width-btn_w*2-10, height=32, 
                                  border_width=0, fg_color="transparent", justify="center")
        self.entry.pack(side="left", fill="x", expand=True)

        self.btn_add = ctk.CTkButton(self, text="+", width=btn_w, height=32, fg_color="transparent", 
                                     hover_color=("gray70", "gray30"), command=self._add)
        self.btn_add.pack(side="right", padx=(0, 2))

    def _sub(self):
        try: v = float(self.var.get())
        except: v = self.max_v
        new_v = max(self.min_v, v - self.inc)
        if isinstance(self.var, tk.IntVar) or isinstance(self.var, ctk.IntVar):
            self.var.set(int(new_v))
        else:
            self.var.set(new_v)

    def _add(self):
        try: v = float(self.var.get())
        except: v = self.min_v
        new_v = min(self.max_v, v + self.inc)
        if isinstance(self.var, tk.IntVar) or isinstance(self.var, ctk.IntVar):
            self.var.set(int(new_v))
        else:
            self.var.set(new_v)


class KillClipperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("王者剪辑  v2.0 (Modern Edition)")
        self.root.geometry("1024x768")
        
        self.video_paths = []
        self.output_dir = ctk.StringVar(value=r"E:\素材\片段")
        self.before     = ctk.DoubleVar(value=10.0)
        self.after      = ctk.DoubleVar(value=1.0)
        self.sample     = ctk.IntVar(value=5)
        self.cooldown   = ctk.DoubleVar(value=2.0)
        
        self.roi_x      = ctk.IntVar(value=1700)
        self.roi_y      = ctk.IntVar(value=18)
        self.roi_w      = ctk.IntVar(value=60)
        self.roi_h      = ctk.IntVar(value=45)
        self.debug_mode = ctk.BooleanVar(value=False)
        self.stop_event = threading.Event()

        self._load_config()
        self._build_ui()
        self._load_history()

    def _load_config(self):
        try:
            if Path(CONFIG_FILE).exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if "output_dir" in cfg: self.output_dir.set(cfg["output_dir"])
                if "before" in cfg: self.before.set(cfg["before"])
                if "after" in cfg: self.after.set(cfg["after"])
                if "sample" in cfg: self.sample.set(cfg["sample"])
                if "cooldown" in cfg: self.cooldown.set(cfg["cooldown"])
                if "roi_x" in cfg: self.roi_x.set(cfg["roi_x"])
                if "roi_y" in cfg: self.roi_y.set(cfg["roi_y"])
                if "roi_w" in cfg: self.roi_w.set(cfg["roi_w"])
                if "roi_h" in cfg: self.roi_h.set(cfg["roi_h"])
                if "debug_mode" in cfg: self.debug_mode.set(cfg["debug_mode"])
        except Exception as e:
            print(f"Failed to load config: {e}")

    def _save_config(self):
        cfg = {
            "output_dir": self.output_dir.get(),
            "before": self.before.get(),
            "after": self.after.get(),
            "sample": self.sample.get(),
            "cooldown": self.cooldown.get(),
            "roi_x": self.roi_x.get(),
            "roi_y": self.roi_y.get(),
            "roi_w": self.roi_w.get(),
            "roi_h": self.roi_h.get(),
            "debug_mode": self.debug_mode.get()
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_history(self):
        try:
            if Path(HISTORY_FILE).exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if history:
                    self._log(f"📖 上次剪辑记录 ({len(history)} 个视频):\n")
                    for h in history[-5:]:
                        self._log(f"   - {Path(h).name}\n")
                    self._log("-" * 55 + "\n\n")
        except:
            pass
            
    def _save_history(self, new_paths):
        history = []
        try:
            if Path(HISTORY_FILE).exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
        except:
            pass
        history.extend(new_paths)
        history = history[-50:]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _build_ui(self):
        # 主容器：分为左右两列
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 左侧面板 (占主导，用于放列表和日志)
        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 20))
        
        # 右侧面板 (固定的配置区)
        right_col = ctk.CTkScrollableFrame(main_container, fg_color="transparent", width=420)
        right_col.pack(side="right", fill="y")

        # --- 左侧内容 ---
        # 标题栏
        header = ctk.CTkFrame(left_col, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header, text="⚔ 王者剪辑  v2.0", font=("Segoe UI", 28, "bold"), text_color=ACCENT).pack(anchor="w")
        ctk.CTkLabel(header, text="基于 EasyOCR 的全自动击杀追踪引擎", font=FONT_SM, text_color="gray").pack(anchor="w")

        # 拖拽区
        self._build_drop_zone(left_col)
        
        # 进度条与终止按钮
        ctrl_row = ctk.CTkFrame(left_col, fg_color="transparent")
        ctrl_row.pack(fill="x", pady=(10, 15))
        
        self.progress_bar = ctk.CTkProgressBar(ctrl_row, progress_color=ACCENT, height=12)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 15))
        self.progress_bar.set(0)

        self.btn_stop = ctk.CTkButton(
            ctrl_row, text="终止", width=80, height=32,
            fg_color=("gray85", "gray25"), hover_color="#e94560",
            state="disabled", command=self._on_stop
        )
        self.btn_stop.pack(side="right")

        # 日志区 (自动填满剩余高度)
        self._build_log(left_col)

        # --- 右侧内容 ---
        # 参数设置
        self._build_params(right_col)

        # ROI 区域
        self._build_roi(right_col)

        # 调试勾选框
        ctk.CTkSwitch(
            right_col, text="开启调试模式（AI 视觉预览区）",
            variable=self.debug_mode, font=FONT_SM,
            progress_color=ACCENT
        ).pack(anchor="w", pady=(20, 10), padx=5)

        # 运行按钮放在右下角
        self.btn_run = ctk.CTkButton(
            right_col, text="▶  开始批量剪辑",
            font=("Segoe UI", 16, "bold"),
            fg_color=ACCENT, text_color="black", hover_color="#dddddd",
            height=50, corner_radius=8,
            command=self._on_run
        )
        self.btn_run.pack(fill="x", pady=(20, 5), padx=5)

    def _build_drop_zone(self, parent):
        zone = ctk.CTkFrame(parent, fg_color=("gray90", "gray15"), corner_radius=12)
        zone.pack(fill="x", pady=(0, 15))

        self.drop_label = ctk.CTkLabel(
            zone, text="🎬 将包含击杀镜头的视频文件拖到此处\n也可以点击本区域多选文件",
            font=("Segoe UI", 14), text_color="gray",
            height=90, cursor="hand2"
        )
        self.drop_label.pack(fill="x", pady=15, padx=20)
        self.drop_label.bind("<Button-1>", lambda e: self._browse_video())
        zone.bind("<Button-1>", lambda e: self._browse_video())

        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self.drop_label.configure(text="🎬 点击本区域选择视频文件\n（未安装 tkinterdnd2，暂不支持拖拽）")

        self.file_label = ctk.CTkLabel(
            zone, text="(未选择文件)", font=FONT_SM, text_color=GREEN, wraplength=550
        )
        self.file_label.pack(pady=(0, 10))

    def _build_params(self, parent):
        card = ctk.CTkFrame(parent, fg_color=("gray85", "gray13"), corner_radius=10)
        card.pack(fill="x", pady=0)

        # 布局采用网格
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="输出目录:", font=FONT_B).grid(row=0, column=0, padx=15, pady=(20, 10), sticky="w")
        row_dir = ctk.CTkFrame(card, fg_color="transparent")
        row_dir.grid(row=0, column=1, padx=15, pady=(20, 10), sticky="we")
        row_dir.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(row_dir, textvariable=self.output_dir, height=32).grid(row=0, column=0, sticky="we")
        ctk.CTkButton(row_dir, text="浏览", width=60, height=32, command=self._browse_output).grid(row=0, column=1, padx=(10, 0))

        opts = [
            ("击杀前保留 (秒)", self.before, 1, 60, 0.5),
            ("击杀后延后 (秒)", self.after,  0, 30, 0.5),
            ("检测采样率 (帧/秒)", self.sample, 1, 30, 1),
            ("连杀防抖冷却 (秒)", self.cooldown, 0.5, 10, 0.5),
        ]

        for i, (lbl, var, f, t, inc) in enumerate(opts, start=1):
            ctk.CTkLabel(card, text=lbl, font=FONT_SM).grid(row=i, column=0, padx=15, pady=8, sticky="w")
            NumInput(card, var, f, t, inc).grid(row=i, column=1, padx=15, pady=8, sticky="w")
            
        # 占位底部 padding
        ctk.CTkFrame(card, height=10, fg_color="transparent").grid(row=len(opts)+1, column=0)

    def _build_roi(self, parent):
        roi_container = ctk.CTkFrame(parent, fg_color="transparent")
        roi_container.pack(fill="x", pady=10)
        
        hdr = ctk.CTkFrame(roi_container, fg_color="transparent")
        hdr.pack(fill="x")
        
        self.roi_btn = ctk.CTkButton(
            hdr, text="▶ 高级：自定义击杀数字侦测区 (ROI)", 
            font=FONT_B, fg_color="transparent", hover_color=("gray80", "gray20"),
            text_color=("black", "white"), anchor="w", command=self._toggle_roi
        )
        self.roi_btn.pack(side="left", fill="x", expand=True)
        
        ctk.CTkButton(
            hdr, text="🎯 截帧校准", width=100, height=30,
            command=self._calibrate_roi
        ).pack(side="right")

        self.roi_panel = ctk.CTkFrame(roi_container, fg_color=("gray90", "gray15"), corner_radius=8)
        # 初始折叠，所以不 pack
        self._roi_visible = False

        roi_cfg = [("X 坐标", self.roi_x), ("Y 坐标", self.roi_y), 
                   ("选区宽度", self.roi_w), ("选区高度", self.roi_h)]
        for i, (lbl, var) in enumerate(roi_cfg):
            f = ctk.CTkFrame(self.roi_panel, fg_color="transparent")
            f.pack(side="left", expand=True, padx=10, pady=15)
            ctk.CTkLabel(f, text=lbl, font=FONT_SM).pack(pady=(0,5))
            ctk.CTkEntry(f, textvariable=var, width=80, justify="center").pack()

    def _toggle_roi(self):
        if self._roi_visible:
            self.roi_panel.pack_forget()
            self.roi_btn.configure(text="▶ 高级：自定义击杀数字侦测区 (ROI)")
        else:
            self.roi_panel.pack(fill="x", pady=(10, 0))
            self.roi_btn.configure(text="▼ 高级：自定义击杀数字侦测区 (ROI)")
        self._roi_visible = not self._roi_visible

    def _build_log(self, parent):
        self.log_text = ctk.CTkTextbox(
            parent, height=200, font=("Consolas", 13), 
            corner_radius=8, fg_color=("gray95", "gray10"),
            border_width=1, border_color=("gray80", "gray25")
        )
        self.log_text.pack(fill="both", expand=True, pady=(0, 10))
        self.log_text.configure(state="disabled")

    # ── 交互逻辑 ────────────────────────────────────────

    def _browse_video(self):
        paths = filedialog.askopenfilenames(
            title="选择视频文件 (可多选)",
            filetypes=[("视频文件", "*.mp4 *.mov *.avi *.mkv *.flv"), ("所有文件", "*.*")]
        )
        if paths:
            self._set_videos(paths)

    def _browse_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir.set(d)

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if paths:
            self._set_videos(paths)

    def _set_videos(self, paths):
        self.video_paths = list(paths)
        names = [Path(p).name for p in self.video_paths]
        lbl = f"✅ 已准备提取 {len(names)} 个视频源" if len(names) > 1 else f"✅ {names[0]}"
        
        self.drop_label.configure(text=lbl, text_color=GREEN, font=("Segoe UI", 16, "bold"))
        self.file_label.configure(text="; ".join(names))
        self._log(f"已加载 {len(self.video_paths)} 个视频片段，等待处理...\n")

    def _calibrate_roi(self):
        if not self.video_paths:
            messagebox.showwarning("提示", "请先在上方拖入至少一个视频供定位使用！")
            return
        vp = self.video_paths[0]
        if not Path(vp).exists():
            messagebox.showerror("错误", f"引用的视频不存在：\n{vp}")
            return

        def _do_calibrate():
            cap = cv2.VideoCapture(vp)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 4))
            ret, frame = cap.read()
            cap.release()
            if not ret:
                self.root.after(0, lambda: messagebox.showerror("错误", "无法读取视频帧用于定位。"))
                return

            h, w = frame.shape[:2]
            scale = min(1.0, 1280 / w)
            disp = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame.copy()

            cv2.putText(disp, "[Cali] Drag to highlight KILL COUNT -> Press SPACE to save / C to cancel", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2)

            roi_sel = cv2.selectROI("Visual ROI Calibration", disp, showCrosshair=True, fromCenter=False)
            cv2.destroyAllWindows()

            rx, ry, rw, rh = roi_sel
            if rw == 0 or rh == 0: return

            rx, ry, rw, rh = int(rx/scale), int(ry/scale), int(rw/scale), int(rh/scale)

            def _apply():
                self.roi_x.set(rx)
                self.roi_y.set(ry)
                self.roi_w.set(rw)
                self.roi_h.set(rh)
                if not self._roi_visible: self._toggle_roi()
                self._log(f"✨ 探测区坐标自动重置完毕: ({rx}, {ry}, {rw}, {rh})\n")
            self.root.after(0, _apply)

        threading.Thread(target=_do_calibrate, daemon=True).start()

    def _on_run(self):
        if not self.video_paths:
            messagebox.showwarning("提示", "你还没给我喂视频文件呢！")
            return
        
        for vp in self.video_paths:
            if not Path(vp).exists():
                messagebox.showerror("错误", f"找不到文件：{vp}")
                return

        self.stop_event.clear()
        self.btn_run.configure(state="disabled", text="⏳  正在疯狂演算中…")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)
        
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _on_stop(self):
        if messagebox.askyesno("终止确认", "确定要强行停止当前的剪辑任务吗？"):
            self.stop_event.set()
            self.btn_stop.configure(state="disabled", text="正在停止...")

    def _run_pipeline(self):
        odir = self.output_dir.get().strip()
        roi  = (self.roi_x.get(), self.roi_y.get(), self.roi_w.get(), self.roi_h.get())
        
        self._save_config()

        total = len(self.video_paths)
        total_clips = 0
        skipped_videos = []
        
        self._log(f"{'='*55}\n🚀 批量识别任务启动 ({total} 枚视频列入队列)\n{'='*55}\n\n")

        for idx, vp in enumerate(self.video_paths, 1):
            if self.stop_event.is_set(): break
            
            v_name = Path(vp).name
            self._log(f"▶ 正在处理 [{idx}/{total}]: {v_name}\n")
            
            try:
                self._log("  📡 [1/2] OCR 深度特征扫描中...\n")
                
                def _update_progress(p):
                    self.root.after(0, lambda: self.progress_bar.set(p))

                timestamps = detect_kills(
                    video_path=vp,
                    roi=roi,
                    sample_rate=self.sample.get(),
                    cooldown=self.cooldown.get(),
                    debug=self.debug_mode.get(),
                    output_dir=odir,
                    log_callback=self._log,
                    progress_callback=_update_progress,
                    stop_event=self.stop_event,
                )

                if self.stop_event.is_set():
                    self._log("🛑 任务已被取消。\n")
                    break

                if not timestamps:
                    self._log("  ⚠ 该视频风平浪静，没有侦测到任何人头，已跳过。\n\n")
                    skipped_videos.append(vp)
                    continue

                self._log("  ✂️ [2/2] 正在调用 FFmpeg 引擎无损裁剪渲染...\n")
                out_files = export_clips(
                    video_path=vp,
                    kill_timestamps=timestamps,
                    output_dir=odir,
                    before=self.before.get(),
                    after=self.after.get(),
                )

                if out_files:
                    total_clips += len(out_files)
                    self._log(f"  🎬 渲染完成！这段视频产出了 {len(out_files)} 个独立操作时刻：\n")
                    for out_file in out_files:
                        self._log(f"     ✅ {Path(out_file).name}\n")
                    self._log("\n")
                else:
                    self._log("  ❌ 丢进剪辑器失败了，是不是没装 FFmpeg？\n\n")

            except Exception as e:
                self._log(f"  ❌ 代码崩了：{e}\n\n")

        if skipped_videos and not self.stop_event.is_set():
            self._log(f"\n{'='*55}\n🚀 开启第二轮复检：对 {len(skipped_videos)} 个未检测到击杀的视频进行细致复查\n{'='*55}\n\n")
            enhanced_sample_rate = min(30, self.sample.get() * 2)
            
            for idx, vp in enumerate(skipped_videos, 1):
                if self.stop_event.is_set(): break
                v_name = Path(vp).name
                self._log(f"▶ [复检] 正在处理 [{idx}/{len(skipped_videos)}]: {v_name} (采样率提升至 {enhanced_sample_rate})\n")
                
                try:
                    self._log("  📡 [1/2] OCR 深度特征扫描中...\n")
                    def _update_progress2(p):
                        self.root.after(0, lambda: self.progress_bar.set(p))
                    timestamps = detect_kills(
                        video_path=vp, roi=roi, sample_rate=enhanced_sample_rate,
                        cooldown=self.cooldown.get(), debug=self.debug_mode.get(),
                        output_dir=odir, log_callback=self._log, progress_callback=_update_progress2,
                        stop_event=self.stop_event
                    )
                    if not timestamps:
                        self._log("  ⚠ 复检依然没有侦测到任何人头，确认跳过。\n\n")
                        continue
                        
                    self._log("  ✂️ [2/2] 正在调用 FFmpeg 引擎无损裁剪渲染...\n")
                    out_files = export_clips(
                        video_path=vp, kill_timestamps=timestamps, output_dir=odir,
                        before=self.before.get(), after=self.after.get()
                    )
                    if out_files:
                        total_clips += len(out_files)
                        self._log(f"  🎬 渲染完成！这段视频产出了 {len(out_files)} 个独立操作时刻：\n")
                        for out_file in out_files:
                            self._log(f"     ✅ {Path(out_file).name}\n")
                        self._log("\n")
                    else:
                        self._log("  ❌ 复检导出失败。\n\n")
                except Exception as e:
                    self._log(f"  ❌ 复检代码崩了：{e}\n\n")

        self._save_history([Path(p).name for p in self.video_paths])

        self._log("=" * 55 + "\n")
        self._log(f"🎉 全部收工！你的私人剪辑师已退下。\n")
        self._log(f"📦 成果汇报: 共搜刮出 {total_clips} 个高能片段。\n")
        self._log(f"📂 存放位置: {Path(odir).resolve()}\n")

        def _reset_btns():
            self.btn_run.configure(state="normal", text="▶ 开始批量剪辑")
            self.btn_stop.configure(state="disabled", text="终止")
            self.progress_bar.set(0 if not self.stop_event.is_set() else self.progress_bar.get())
            
        self.root.after(0, _reset_btns)

    def _log(self, text: str):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _append)


def main():
    if HAS_DND:
        root = CTk_TkinterDnD()
    else:
        root = ctk.CTk()
        
    try:
        if os.name == 'nt':
            root.state('zoomed')
    except Exception:
        pass
        
    # Windows 任务栏及窗口图标
    try:
        root.iconbitmap("王者.ico")
    except Exception:
        pass
        
    app = KillClipperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
