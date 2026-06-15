"""
考试试卷生成系统 - 图形用户界面(GUI)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
from core import ExamCore
from docx_utils import export_to_word
from config import DEFAULT_EXAM_TITLE, DEFAULT_STUDENT_INFO, VERSION

# 题型注册表（加新题型只需在此加一行）
QUESTION_TYPES = [
    {"key": "judgment",   "label": "判断题", "score": 1, "default": 1},
    {"key": "mcq",        "label": "单选题", "score": 1, "default": 1},
    {"key": "mcq_multi",  "label": "多选题", "score": 2, "default": 0},
]
QT_MAP = {qt["key"]: qt for qt in QUESTION_TYPES}
TYPE_NAME = {qt["key"]: qt["label"] for qt in QUESTION_TYPES}
TYPE_KEY = {qt["label"]: qt["key"] for qt in QUESTION_TYPES}


class ExamGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"考试试卷生成系统 v{VERSION}")
        self.root.geometry("1000x850")
        self.root.configure(bg="#f0f8ff")
        self.exam_core = ExamCore()

        # 题型数据（可排序、可开关）
        self.question_types = [dict(qt) for qt in QUESTION_TYPES]
        self.q_vars = {}       # key -> IntVar
        self.q_counts = {}     # key -> Combobox
        self.q_scores = {}     # key -> Spinbox (每題分數)
        self.q_ratios = {}     # key -> Combobox (比例模式)
        self.q_starts = {}     # key -> Combobox (顺序模式)
        self.q_ends = {}       # key -> Combobox (顺序模式)

        self.create_widgets()

    # ═══════════════════════════════════════════
    # UI 构建
    # ═══════════════════════════════════════════

    def create_widgets(self):
        title_frame = tk.Frame(self.root, bg="#4682b4", height=60)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(title_frame, text=f"考试试卷生成系统 v{VERSION}",
                 font=("微软雅黑", 18, "bold"), fg="white", bg="#4682b4").pack(pady=15)

        main_frame = tk.Frame(self.root, bg="#f0f8ff")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ── 左侧面板 ──
        left_frame = tk.LabelFrame(main_frame, text="文件与设置", font=("微软雅黑", 10, "bold"),
                                   bg="#f0f8ff", padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        r = -1

        r += 1
        tk.Label(left_frame, text="题库文件:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.file_path_var = tk.StringVar()
        self.file_entry = tk.Entry(left_frame, textvariable=self.file_path_var, width=22, font=("微软雅黑", 9))
        self.file_entry.grid(row=r, column=1, sticky=tk.W+tk.E, padx=(0, 5))
        tk.Button(left_frame, text="浏览...", command=self.browse_file,
                  bg="#2196f3", fg="white", font=("微软雅黑", 9)).grid(row=r, column=2, padx=(0, 2))
        tk.Button(left_frame, text="模板", command=self.open_template,
                  bg="#9e9e9e", fg="white", font=("微软雅黑", 9), width=3).grid(row=r, column=3)

        r += 1
        tk.Label(left_frame, text="试卷标题:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.exam_title = tk.Entry(left_frame, width=25, font=("微软雅黑", 9))
        self.exam_title.insert(0, DEFAULT_EXAM_TITLE)
        self.exam_title.grid(row=r, column=1, columnspan=2, sticky=tk.W+tk.E)
        self.exam_title.bind("<KeyRelease>", lambda e: self._schedule_auto_preview())

        r += 1
        tk.Label(left_frame, text="考生信息:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.student_name = tk.Entry(left_frame, width=25, font=("微软雅黑", 9))
        self.student_name.insert(0, DEFAULT_STUDENT_INFO)
        self.student_name.grid(row=r, column=1, columnspan=2, sticky=tk.W+tk.E)
        self.student_name.bind("<KeyRelease>", lambda e: self._schedule_auto_preview())

        r += 1
        tk.Label(left_frame, text="考试时间(分):", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.exam_time = ttk.Combobox(left_frame, values=["", "30", "45", "60", "90", "120", "150", "180"], width=10)
        self.exam_time.set("")
        self.exam_time.grid(row=r, column=1, columnspan=2, sticky=tk.W)
        self.exam_time.bind("<<ComboboxSelected>>", lambda e: self._schedule_auto_preview())

        r += 1
        tk.Label(left_frame, text="纸张:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.paper_size = ttk.Combobox(left_frame, values=["A4", "A3", "B5", "Letter"], width=8)
        self.paper_size.current(0)
        self.paper_size.grid(row=r, column=1, sticky=tk.W)

        r += 1
        tk.Label(left_frame, text="页眉:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.header_text = tk.Entry(left_frame, width=22, font=("微软雅黑", 9))
        self.header_text.insert(0, "")
        self.header_text.grid(row=r, column=1, columnspan=2, sticky=tk.W+tk.E)
        self.header_text.bind("<KeyRelease>", lambda e: self._schedule_auto_preview())

        r += 1
        tk.Label(left_frame, text="导出模式:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.export_mode = ttk.Combobox(left_frame, values=["随机抽取", "按比例导出", "顺序导出"], width=10)
        self.export_mode.current(0)
        self.export_mode.grid(row=r, column=1, columnspan=2, sticky=tk.W)
        self.export_mode.bind("<<ComboboxSelected>>", self.on_export_mode_change)

        # ── 试题类型列表 ──
        r += 1
        type_label = tk.Label(left_frame, text="试题类型", bg="#f0f8ff", font=("微软雅黑", 10, "bold"))
        type_label.grid(row=r, column=0, columnspan=3, sticky=tk.W, pady=(10, 2))

        self.type_list_frame = tk.Frame(left_frame, bg="#f0f8ff")
        r += 1
        self.type_list_frame.grid(row=r, column=0, columnspan=3, sticky=tk.W+tk.E, pady=2)
        self._build_type_rows()

        # ── 比例设置（默认隐藏） ──
        r += 1
        self.ratio_frame = tk.Frame(left_frame, bg="#f0f8ff")
        self.ratio_frame.grid(row=r, column=0, columnspan=3, sticky=tk.W+tk.E, pady=4)
        self._build_ratio_settings()
        self.ratio_frame.grid_remove()

        # ── 顺序范围设置（默认隐藏） ──
        r += 1
        self.sequential_frame = tk.Frame(left_frame, bg="#f0f8ff")
        self.sequential_frame.grid(row=r, column=0, columnspan=3, sticky=tk.W+tk.E, pady=4)
        self._build_sequential_settings()
        self.sequential_frame.grid_remove()

        # ── 其他设置 ──
        r += 1
        self.answer_var = tk.IntVar(value=0)
        tk.Checkbutton(left_frame, text="包含答案", variable=self.answer_var, bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, columnspan=3, sticky=tk.W, pady=4)

        r += 1
        self.random_order_var = tk.IntVar(value=1)
        tk.Checkbutton(left_frame, text="随机排序题目", variable=self.random_order_var, bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, columnspan=3, sticky=tk.W, pady=4)

        r += 1
        tk.Label(left_frame, text="生成试卷数量:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=r, column=0, sticky=tk.W, pady=4)
        self.exam_count = ttk.Combobox(left_frame, values=["1", "2", "3", "4", "5"], width=5)
        self.exam_count.current(0)
        self.exam_count.grid(row=r, column=1, sticky=tk.W)

        r += 1
        self.auto_refresh_var = tk.IntVar(value=0)
        tk.Checkbutton(left_frame, text="自动刷新预览", variable=self.auto_refresh_var, bg="#f0f8ff",
                       font=("微软雅黑", 9), command=self._on_auto_refresh_toggle).grid(
            row=r, column=0, columnspan=3, sticky=tk.W, pady=4)

        # ── 右侧面板 ──
        right_frame = tk.Frame(main_frame, bg="#f0f8ff")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        preview_frame = tk.LabelFrame(right_frame, text="试卷预览", font=("微软雅黑", 10, "bold"), bg="#f0f8ff", padx=10, pady=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=20, width=70, font=("微软雅黑", 9), wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        info_frame = tk.Frame(right_frame, bg="#fff8e1", relief=tk.GROOVE, bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        self.info_var = tk.StringVar(value="试卷信息: 请生成预览")
        tk.Label(info_frame, textvariable=self.info_var, bg="#fff8e1",
                 font=("微软雅黑", 9), anchor=tk.W).pack(fill=tk.X, padx=10, pady=4)

        btn_frame = tk.Frame(right_frame, bg="#f0f8ff")
        btn_frame.pack(fill=tk.X, pady=5)

        for text, cmd, color in [
            ("加载题库", self.load_excel, "#ff9800"),
            ("生成预览", self.generate_preview, "#4caf50"),
            ("导出Word", self.export_word, "#2196f3"),
        ]:
            tk.Button(btn_frame, text=text, command=cmd,
                      bg=color, fg="white", font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_frame, text="保存模板", command=self.save_template,
                  bg="#9c27b0", fg="white", font=("微软雅黑", 10), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="加载模板", command=self.load_template,
                  bg="#673ab7", fg="white", font=("微软雅黑", 10), width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="退出系统", command=self.root.quit,
                  bg="#f44336", fg="white", font=("微软雅黑", 10), width=8).pack(side=tk.RIGHT, padx=3)

        self.status_var = tk.StringVar(value=f"系统版本: v{VERSION} | 请选择Excel题库文件")
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                 font=("微软雅黑", 9), bg="#e3f2fd").pack(side=tk.BOTTOM, fill=tk.X)

    # ── 题型行 ──

    def _rebuild_type_rows(self):
        """刷新题型行（排序变化后调用）"""
        saved = {}
        for key, cb in self.q_counts.items():
            try:
                saved[key] = cb.get()
            except Exception:
                saved[key] = ''
        saved_scores = {}
        for key, sp in self.q_scores.items():
            try:
                saved_scores[key] = sp.get()
            except Exception:
                saved_scores[key] = ''
        for w in self.type_list_frame.winfo_children():
            w.destroy()
        self.q_counts.clear()
        self.q_scores.clear()
        self._build_type_rows(saved, saved_scores)

    def _build_type_rows(self, saved_values=None, saved_scores=None):
        """从 question_types 列表构建题型行"""
        if saved_values is None:
            saved_values = {}
        if saved_scores is None:
            saved_scores = {}
        for idx, qt in enumerate(self.question_types):
            key = qt["key"]
            row = tk.Frame(self.type_list_frame, bg="#f0f8ff")
            row.pack(fill=tk.X, pady=1)

            # Checkbox
            if key not in self.q_vars:
                self.q_vars[key] = tk.IntVar(value=qt.get("default", 0))
            cb = tk.Checkbutton(row, variable=self.q_vars[key], bg="#f0f8ff")
            cb.pack(side=tk.LEFT)

            # 标签
            tk.Label(row, text=qt["label"], bg="#f0f8ff", font=("微软雅黑", 9),
                     width=6, anchor=tk.W).pack(side=tk.LEFT)

            # 数量
            tk.Label(row, text="数量:", bg="#f0f8ff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
            cb = ttk.Combobox(row, values=[], width=4)
            old = saved_values.get(key, '')
            if old:
                cb.set(old)
            cb.pack(side=tk.LEFT, padx=(0, 4))
            self.q_counts[key] = cb
            cb.bind("<<ComboboxSelected>>", lambda e: self._schedule_auto_preview())

            # 分数
            tk.Label(row, text="分:", bg="#f0f8ff", font=("微软雅黑", 9)).pack(side=tk.LEFT)
            sp = ttk.Spinbox(row, from_=1, to=20, width=3)
            default_score = saved_scores.get(key, str(qt.get("score", 1)))
            sp.set(default_score)
            sp.pack(side=tk.LEFT, padx=(0, 8))
            self.q_scores[key] = sp

            # 上移/下移
            up_btn = tk.Button(row, text="↑", width=2, font=("微软雅黑", 8),
                               command=lambda i=idx: self._move_type(i, -1))
            up_btn.pack(side=tk.LEFT, padx=1)
            down_btn = tk.Button(row, text="↓", width=2, font=("微软雅黑", 8),
                                 command=lambda i=idx: self._move_type(i, 1))
            down_btn.pack(side=tk.LEFT, padx=1)

            if idx == 0:
                up_btn.config(state=tk.DISABLED)
            if idx == len(self.question_types) - 1:
                down_btn.config(state=tk.DISABLED)

    def _move_type(self, idx, direction):
        """移动题型位置"""
        target = idx + direction
        if target < 0 or target >= len(self.question_types):
            return
        self.question_types[idx], self.question_types[target] = \
            self.question_types[target], self.question_types[idx]
        self._rebuild_type_rows()

    # ── 比例/顺序设置（动态生成） ──

    def _build_ratio_settings(self):
        title = tk.Label(self.ratio_frame, text="比例设置: ", bg="#f0f8ff", font=("微软雅黑", 9))
        title.pack(side=tk.LEFT)
        for qt in self.question_types:
            key = qt["key"]
            tk.Label(self.ratio_frame, text=f'{qt["label"]}%:', bg="#f0f8ff",
                     font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(5, 0))
            cb = ttk.Combobox(self.ratio_frame, values=["10", "20", "30", "40", "50", "60", "70"], width=4)
            cb.set("20" if key == "judgment" else "40" if key == "mcq" else "10")
            self.q_ratios[key] = cb
            cb.pack(side=tk.LEFT, padx=2)

        tk.Label(self.ratio_frame, text="  总题数:", bg="#f0f8ff", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.total_questions_cb = ttk.Combobox(self.ratio_frame, values=["100", "120", "150", "200"], width=4)
        self.total_questions_cb.current(0)
        self.total_questions_cb.pack(side=tk.LEFT, padx=2)

    def _build_sequential_settings(self):
        tk.Label(self.sequential_frame, text="题型范围: ", bg="#f0f8ff",
                 font=("微软雅黑", 9)).pack(side=tk.LEFT)
        for qt in self.question_types:
            key = qt["key"]
            tk.Label(self.sequential_frame, text=qt["label"], bg="#f0f8ff",
                     font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=(5, 0))
            s = ttk.Combobox(self.sequential_frame, values=[], width=3)
            self.q_starts[key] = s
            s.pack(side=tk.LEFT)
            tk.Label(self.sequential_frame, text="-", bg="#f0f8ff").pack(side=tk.LEFT)
            e = ttk.Combobox(self.sequential_frame, values=[], width=3)
            self.q_ends[key] = e
            e.pack(side=tk.LEFT)

    # ── 配置构建 ──

    def _build_config(self):
        """从 UI 构建配置字典"""
        mode = self.export_mode.get()
        is_ratio = mode == "按比例导出"
        is_seq = mode == "顺序导出"

        def int_or(v, default=0):
            try:
                return int(v)
            except (ValueError, TypeError, AttributeError):
                return default

        config = {
            'export_mode': mode,
            'include_answers': bool(self.answer_var.get()),
            'exam_title': self.exam_title.get(),
            'student_name': self.student_name.get(),
            'exam_time': self.exam_time.get(),
            'paper_size': self.paper_size.get(),
            'header_text': self.header_text.get().strip(),
            'random_order': bool(self.random_order_var.get()),
            'question_order': [qt["key"] for qt in self.question_types],
        }

        for qt in self.question_types:
            key = qt["key"]
            config[f'include_{key}'] = bool(self.q_vars[key].get())
            config[f'{key}_count'] = int_or(self.q_counts[key].get()) if self.q_vars[key].get() else 0
            config[f'{key}_score'] = int_or(self.q_scores[key].get(), qt.get("score", 1))
            if is_ratio:
                config[f'{key}_ratio'] = int_or(self.q_ratios[key].get())
            if is_seq:
                config[f'{key}_start'] = int_or(self.q_starts[key].get())
                config[f'{key}_end'] = int_or(self.q_ends[key].get())

        if is_ratio:
            config['total_questions'] = int_or(self.total_questions_cb.get())

        return config

    def _apply_config(self, cfg):
        """将配置应用到 UI 控件（加载模板）"""
        self.exam_title.delete(0, tk.END)
        self.exam_title.insert(0, cfg.get('exam_title', DEFAULT_EXAM_TITLE))
        self.student_name.delete(0, tk.END)
        self.student_name.insert(0, cfg.get('student_name', DEFAULT_STUDENT_INFO))
        self.exam_time.set(cfg.get('exam_time', ''))
        self.paper_size.set(cfg.get('paper_size', 'A4'))
        self.header_text.delete(0, tk.END)
        self.header_text.insert(0, cfg.get('header_text', ''))

        mode = cfg.get('export_mode', '随机抽取')
        if mode in ["随机抽取", "按比例导出", "顺序导出"]:
            self.export_mode.set(mode)
            self.on_export_mode_change(None)

        # 加载题型顺序
        order = cfg.get('question_order')
        if order:
            ordered = []
            for key in order:
                found = [qt for qt in self.question_types if qt["key"] == key]
                if found:
                    ordered.append(found[0])
            if ordered:
                self.question_types = ordered
                self._rebuild_type_rows()

        def set_cb(cb, val):
            cb.set(str(val) if val else '')

        for qt in self.question_types:
            key = qt["key"]
            self.q_vars[key].set(1 if cfg.get(f'{key}_count', 0) > 0 else 0)
            set_cb(self.q_counts[key], cfg.get(f'{key}_count'))
            set_cb(self.q_scores.get(key), cfg.get(f'{key}_score', qt.get("score", 1)))
            set_cb(self.q_ratios.get(key), cfg.get(f'{key}_ratio'))
            set_cb(self.q_starts.get(key), cfg.get(f'{key}_start'))
            set_cb(self.q_ends.get(key), cfg.get(f'{key}_end'))

        set_cb(self.total_questions_cb, cfg.get('total_questions'))
        self.answer_var.set(1 if cfg.get('include_answers') else 0)
        self.random_order_var.set(1 if cfg.get('random_order', True) else 0)
        set_cb(self.exam_count, cfg.get('exam_count', 1))

    def _extract_template_data(self):
        cfg = self._build_config()
        for key in list(cfg.keys()):
            if key.endswith('_start') or key.endswith('_end'):
                cfg.pop(key, None)
        cfg['__template_version'] = VERSION
        return cfg

    # ── UI 回调 ──

    def on_export_mode_change(self, event):
        mode = self.export_mode.get()
        self.ratio_frame.pack_forget() if mode != "按比例导出" else None
        self.sequential_frame.pack_forget() if mode != "顺序导出" else None
        # Rebuild ratio/sequential in correct visibility
        if mode == "按比例导出":
            self.ratio_frame.pack(fill=tk.X, pady=4)
        elif mode == "顺序导出":
            self.sequential_frame.pack(fill=tk.X, pady=4)

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")])
        if path:
            self.file_path_var.set(path)
            self.exam_core.excel_path = path
            self.status_var.set(f"系统版本: v{VERSION} | 已选择文件: {os.path.basename(path)}")

    def open_template(self):
        """打开题库模板文件"""
        template_path = os.path.join(os.path.dirname(__file__), "题库模板.xlsx")
        if os.path.exists(template_path):
            self.file_path_var.set(template_path)
            self.exam_core.excel_path = template_path
            self.status_var.set(f"系统版本: v{VERSION} | 已加载模板: 题库模板.xlsx")
            self.load_excel()
        else:
            messagebox.showerror("错误", "模板文件不存在: 题库模板.xlsx\n请确认文件在项目根目录下。")

    def load_excel(self):
        try:
            self.exam_core.load_excel(self.file_path_var.get())
            for qt in self.question_types:
                key = qt["key"]
                name = qt["label"]
                count = self.exam_core.get_question_type_count(name)
                cb = self.q_counts[key]
                cb['values'] = list(range(1, count + 1)) if count > 0 else []
                cb.current(0) if count > 0 else self.q_vars[key].set(0)

                for combos in [(self.q_starts, self.q_ends)]:
                    s = combos[0].get(key)
                    e = combos[1].get(key)
                    if s and e:
                        nums = list(range(1, count + 1)) if count > 0 else []
                        s['values'] = nums
                        e['values'] = nums
                        if nums:
                            s.current(0)
                            e.current(len(nums) - 1)

            jc = self.exam_core.get_question_type_count('判断题')
            mc = self.exam_core.get_question_type_count('单选题')
            mmc = self.exam_core.get_question_type_count('多选题')
            self.status_var.set(f"系统版本: v{VERSION} | 题库加载成功: {jc}道判断题, {mc}道单选题, {mmc}道多选题")
        except Exception as e:
            messagebox.showerror("错误", f"加载Excel文件失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 加载失败")

    def _update_info_bar(self, total_count, all_answers):
        parts = [f"共 {total_count} 题"]
        if all_answers:
            total_score = 0
            for qt in self.question_types:
                key = qt["key"]
                cnt = len([a for a in all_answers if a[2] == qt["label"]])
                score_per = int(self.q_scores.get(key, {}).get() if hasattr(self.q_scores.get(key, {}), 'get') else qt.get("score", 1))
                try:
                    score_per = int(self.q_scores[key].get())
                except Exception:
                    score_per = qt.get("score", 1)
                s = cnt * score_per
                total_score += s
                parts.append(f"{qt['label']} {cnt} 题×{score_per}分={s}分")
            parts.append(f"总分 {total_score} 分")
        self.info_var.set("试卷信息: " + " | ".join(parts))

    _auto_preview_timer = None

    def _on_auto_refresh_toggle(self):
        """自动刷新开关切换"""
        if self.auto_refresh_var.get():
            self._schedule_auto_preview()

    def _schedule_auto_preview(self):
        """延时刷新预览（800ms 防抖）"""
        if not self.auto_refresh_var.get():
            return
        if self._auto_preview_timer:
            self.root.after_cancel(self._auto_preview_timer)
        self._auto_preview_timer = self.root.after(800, self._do_auto_preview)

    def _do_auto_preview(self):
        """执行自动预览刷新"""
        self._auto_preview_timer = None
        if not self.auto_refresh_var.get():
            return
        if not self.exam_core.exam_data is None:
            try:
                config = self._build_config()
                content, total = self.exam_core.generate_preview(config)
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, content)
                self._update_info_bar(total, None)
                self.status_var.set(f"系统版本: v{VERSION} | 共{total}道题 | 自动刷新")
            except Exception:
                pass  # 自动刷新静默失败，避免频繁弹窗

    def generate_preview(self):
        try:
            config = self._build_config()
            content, total = self.exam_core.generate_preview(config)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, content)
            self.status_var.set(f"系统版本: v{VERSION} | 预览生成完成: 共{total}道题")
            self._update_info_bar(total, None)
        except Exception as e:
            messagebox.showerror("错误", f"生成预览失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 生成预览失败")

    def export_word(self):
        try:
            config = self._build_config()
            count = int(self.exam_count.get())
            datas = self.exam_core.generate_exam_datas(config, count)
            export_to_word(datas, config, count)
            if datas:
                self._update_info_bar(datas[0]['total_count'], datas[0]['all_answers'])
            self.status_var.set(f"系统版本: v{VERSION} | 已成功生成 {count} 份试卷")
            messagebox.showinfo("成功", f"已成功生成 {count} 份试卷")
        except Exception as e:
            messagebox.showerror("错误", f"导出Word失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 导出失败")

    def save_template(self):
        data = self._extract_template_data()
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("模板文件", "*.json"), ("所有文件", "*.*")],
            initialfile="试卷模板.json")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status_var.set(f"系统版本: v{VERSION} | 模板已保存: {os.path.basename(path)}")
            messagebox.showinfo("成功", "模板保存成功")
        except Exception as e:
            messagebox.showerror("错误", f"保存模板失败:\n{str(e)}")

    def load_template(self):
        path = filedialog.askopenfilename(filetypes=[("模板文件", "*.json"), ("所有文件", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_config(data)
            self.status_var.set(f"系统版本: v{VERSION} | 模板已加载: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("错误", f"加载模板失败:\n{str(e)}")
