"""
考试试卷生成系统 - 图形用户界面(GUI)

功能：
1. 创建应用程序主界面
2. 处理用户交互事件
3. 调用核心业务逻辑
4. 显示预览和状态信息

接口：
- ExamGeneratorGUI(root): 主GUI类
  - browse_file(): 浏览Excel文件
  - load_excel(): 加载Excel题库
  - generate_preview(): 生成试卷预览
  - export_word(): 导出Word文档

依赖：
- core.ExamCore
- docx_utils
- config
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
from core import ExamCore
from docx_utils import export_to_word
from config import DEFAULT_EXAM_TITLE, DEFAULT_STUDENT_INFO, VERSION

class ExamGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"考试试卷生成系统 v{VERSION}")
        self.root.geometry("1000x800")
        self.root.configure(bg="#f0f8ff")
        
        # 初始化核心业务逻辑
        self.exam_core = ExamCore()
        
        # 创建UI
        self.create_widgets()
    
    def create_widgets(self):
        # 标题
        title_frame = tk.Frame(self.root, bg="#4682b4", height=60)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_label = tk.Label(title_frame, text=f"考试试卷生成系统 v{VERSION}", 
                             font=("微软雅黑", 18, "bold"), fg="white", bg="#4682b4")
        title_label.pack(pady=15)
        
        # 主内容区
        main_frame = tk.Frame(self.root, bg="#f0f8ff")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 左侧面板 - 文件选择和设置
        left_frame = tk.LabelFrame(main_frame, text="文件与设置", font=("微软雅黑", 10, "bold"), 
                                 bg="#f0f8ff", padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Excel文件选择
        tk.Label(left_frame, text="题库文件:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.file_path_var = tk.StringVar()
        self.file_entry = tk.Entry(left_frame, textvariable=self.file_path_var, width=25, font=("微软雅黑", 9))
        self.file_entry.grid(row=0, column=1, sticky=tk.W+tk.E, padx=(0, 5))
        
        tk.Button(left_frame, text="浏览...", command=self.browse_file, 
                 bg="#2196f3", fg="white", font=("微软雅黑", 9)).grid(row=0, column=2)
        
        # 试卷设置
        tk.Label(left_frame, text="试卷标题:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.exam_title = tk.Entry(left_frame, width=25, font=("微软雅黑", 9))
        self.exam_title.insert(0, DEFAULT_EXAM_TITLE)
        self.exam_title.grid(row=1, column=1, columnspan=2, sticky=tk.W+tk.E)
        
        tk.Label(left_frame, text="考生信息:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.student_name = tk.Entry(left_frame, width=25, font=("微软雅黑", 9))
        self.student_name.insert(0, DEFAULT_STUDENT_INFO)
        self.student_name.grid(row=2, column=1, columnspan=2, sticky=tk.W+tk.E)
        
        # 导出模式选择
        tk.Label(left_frame, text="导出模式:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.export_mode = ttk.Combobox(left_frame, values=["随机抽取", "按比例导出", "顺序导出"], width=10)
        self.export_mode.current(0)
        self.export_mode.grid(row=3, column=1, columnspan=2, sticky=tk.W)
        self.export_mode.bind("<<ComboboxSelected>>", self.on_export_mode_change)
        
        # 比例设置（默认隐藏）
        self.ratio_frame = tk.Frame(left_frame, bg="#f0f8ff")
        self.ratio_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        tk.Label(self.ratio_frame, text="判断题比例:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=0, sticky=tk.W)
        self.judgment_ratio = ttk.Combobox(self.ratio_frame, values=["10%", "20%", "30%", "40%"], width=5)
        self.judgment_ratio.current(1)  # 默认20%
        self.judgment_ratio.grid(row=0, column=1, sticky=tk.W, padx=(5, 10))
        
        tk.Label(self.ratio_frame, text="单选题比例:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=2, sticky=tk.W)
        self.mcq_ratio = ttk.Combobox(self.ratio_frame, values=["30%", "40%", "50%", "60%"], width=5)
        self.mcq_ratio.current(1)  # 默认40%
        self.mcq_ratio.grid(row=0, column=3, sticky=tk.W)
        
        tk.Label(self.ratio_frame, text="多选题比例:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=4, sticky=tk.W)
        self.mcq_multi_ratio = ttk.Combobox(self.ratio_frame, values=["10%", "20%", "30%", "40%"], width=5)
        self.mcq_multi_ratio.current(0)  # 默认10%
        self.mcq_multi_ratio.grid(row=0, column=5, sticky=tk.W)
        
        # 总题数设置（用于按比例导出）
        tk.Label(self.ratio_frame, text="总题数:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.total_questions_cb = ttk.Combobox(self.ratio_frame, values=["100", "120", "150", "200"], width=5)
        self.total_questions_cb.current(0)  # 默认100
        self.total_questions_cb.grid(row=1, column=1, sticky=tk.W, padx=(5, 10))
        
        # 顺序导出设置（默认隐藏）
        self.sequential_frame = tk.Frame(left_frame, bg="#f0f8ff")
        self.sequential_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        tk.Label(self.sequential_frame, text="判断题范围:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=0, sticky=tk.W)
        self.judgment_start = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.judgment_start.grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
        tk.Label(self.sequential_frame, text="-", bg="#f0f8ff").grid(row=0, column=2)
        self.judgment_end = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.judgment_end.grid(row=0, column=3, sticky=tk.W, padx=(5, 10))
        
        tk.Label(self.sequential_frame, text="单选题范围:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=0, column=4, sticky=tk.W)
        self.mcq_start = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.mcq_start.grid(row=0, column=5, sticky=tk.W, padx=(0, 5))
        tk.Label(self.sequential_frame, text="-", bg="#f0f8ff").grid(row=0, column=6)
        self.mcq_end = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.mcq_end.grid(row=0, column=7, sticky=tk.W)
        
        # 多选题范围设置
        tk.Label(self.sequential_frame, text="多选题范围:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mcq_multi_start = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.mcq_multi_start.grid(row=1, column=1, sticky=tk.W, padx=(0, 5))
        tk.Label(self.sequential_frame, text="-", bg="#f0f8ff").grid(row=1, column=2)
        self.mcq_multi_end = ttk.Combobox(self.sequential_frame, values=[], width=5)
        self.mcq_multi_end.grid(row=1, column=3, sticky=tk.W, padx=(5, 10))
        
        # 默认隐藏设置
        self.ratio_frame.grid_remove()
        self.sequential_frame.grid_remove()
        
        # 题型选择
        tk.Label(left_frame, text="试题类型选择", bg="#f0f8ff", font=("微软雅黑", 10, "bold")).grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
        
        # 题型顺序选择
        tk.Label(left_frame, text="题型顺序:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.type_order = ttk.Combobox(left_frame, values=["判断题→单选题", "单选题→判断题"], width=15)
        self.type_order.current(0)
        self.type_order.grid(row=6, column=1, columnspan=2, sticky=tk.W)
        
        # 判断题
        self.judgment_var = tk.IntVar(value=1)
        tk.Checkbutton(left_frame, text="判断题", variable=self.judgment_var, 
                      bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=7, column=0, sticky=tk.W)
        
        tk.Label(left_frame, text="数量:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=7, column=1, sticky=tk.W)
        self.judgment_count = ttk.Combobox(left_frame, values=[], width=5)
        self.judgment_count.grid(row=7, column=2, sticky=tk.W)
        
        # 单选题
        self.mcq_var = tk.IntVar(value=1)
        tk.Checkbutton(left_frame, text="单选题", variable=self.mcq_var, 
                      bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=8, column=0, sticky=tk.W, pady=5)
        
        tk.Label(left_frame, text="数量:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=8, column=1, sticky=tk.W)
        self.mcq_count = ttk.Combobox(left_frame, values=[], width=5)
        self.mcq_count.grid(row=8, column=2, sticky=tk.W)
        
        # 多选题（新增）
        self.mcq_multi_var = tk.IntVar(value=0)
        tk.Checkbutton(left_frame, text="多选题", variable=self.mcq_multi_var, 
                      bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=9, column=0, sticky=tk.W, pady=5)
        
        tk.Label(left_frame, text="数量:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=9, column=1, sticky=tk.W)
        self.mcq_multi_count = ttk.Combobox(left_frame, values=[], width=5)
        self.mcq_multi_count.grid(row=9, column=2, sticky=tk.W)
        
        # 答案选项
        self.answer_var = tk.IntVar(value=0)
        tk.Checkbutton(left_frame, text="包含答案", variable=self.answer_var, 
                      bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=10, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # 随机排序选项
        self.random_order_var = tk.IntVar(value=1)
        tk.Checkbutton(left_frame, text="随机排序题目", variable=self.random_order_var, 
                      bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=11, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # 试卷数量设置
        tk.Label(left_frame, text="生成试卷数量:", bg="#f0f8ff", font=("微软雅黑", 9)).grid(row=12, column=0, sticky=tk.W, pady=5)
        self.exam_count = ttk.Combobox(left_frame, values=["1", "2", "3", "4", "5"], width=5)
        self.exam_count.current(0)
        self.exam_count.grid(row=12, column=1, sticky=tk.W)
        
        # 右侧面板 - 预览和操作
        right_frame = tk.Frame(main_frame, bg="#f0f8ff")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 预览区域
        preview_frame = tk.LabelFrame(right_frame, text="试卷预览", font=("微软雅黑", 10, "bold"), 
                                    bg="#f0f8ff", padx=10, pady=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=20, width=70, 
                                                    font=("微软雅黑", 9), wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        
        # 按钮区域
        btn_frame = tk.Frame(right_frame, bg="#f0f8ff")
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="加载题库", command=self.load_excel, 
                 bg="#ff9800", fg="white", font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="生成预览", command=self.generate_preview, 
                 bg="#4caf50", fg="white", font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="导出Word", command=self.export_word, 
                 bg="#2196f3", fg="white", font=("微软雅黑", 10), width=10).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="退出系统", command=self.root.quit, 
                 bg="#f44336", fg="white", font=("微软雅黑", 10), width=10).pack(side=tk.RIGHT, padx=5)
        
        # 状态栏
        self.status_var = tk.StringVar(value=f"系统版本: v{VERSION} | 请选择Excel题库文件")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                            font=("微软雅黑", 9), bg="#e3f2fd")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_export_mode_change(self, event):
        """导出模式改变时显示/隐藏比例设置"""
        mode = self.export_mode.get()
        if mode == "按比例导出":
            self.ratio_frame.grid()
            self.sequential_frame.grid_remove()
        elif mode == "顺序导出":
            self.sequential_frame.grid()
            self.ratio_frame.grid_remove()
        else:  # 随机抽取
            self.ratio_frame.grid_remove()
            self.sequential_frame.grid_remove()
    
    def browse_file(self):
        """浏览Excel文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)
            self.exam_core.excel_path = file_path
            self.status_var.set(f"系统版本: v{VERSION} | 已选择文件: {os.path.basename(file_path)}")
    
    def load_excel(self):
        """加载Excel题库"""
        try:
            # 加载Excel数据
            self.exam_core.load_excel(self.file_path_var.get())
            
            # 更新UI
            judgment_count = self.exam_core.get_question_type_count('判断题')
            mcq_count = self.exam_core.get_question_type_count('单选题')
            mcq_multi_count = self.exam_core.get_question_type_count('多选题')
            
            # 更新判断题UI
            if judgment_count > 0:
                self.judgment_count['values'] = list(range(1, judgment_count + 1))
                self.judgment_count.current(0)
            else:
                self.judgment_count['values'] = []
                self.judgment_var.set(0)
            
            # 更新单选题UI
            if mcq_count > 0:
                self.mcq_count['values'] = list(range(1, mcq_count + 1))
                self.mcq_count.current(0)
            else:
                self.mcq_count['values'] = []
                self.mcq_var.set(0)
            
            # 更新多选题UI
            if mcq_multi_count > 0:
                self.mcq_multi_count['values'] = list(range(1, mcq_multi_count + 1))
                self.mcq_multi_count.current(0)
            else:
                self.mcq_multi_count['values'] = []
                self.mcq_multi_var.set(0)
            
            # 更新顺序导出范围
            if judgment_count > 0:
                judgment_numbers = self.exam_core.get_question_numbers('判断题')
                self.judgment_start['values'] = judgment_numbers
                self.judgment_end['values'] = judgment_numbers
                self.judgment_start.current(0)
                self.judgment_end.current(len(judgment_numbers) - 1)
            else:
                self.judgment_start['values'] = []
                self.judgment_end['values'] = []
            
            if mcq_count > 0:
                mcq_numbers = self.exam_core.get_question_numbers('单选题')
                self.mcq_start['values'] = mcq_numbers
                self.mcq_end['values'] = mcq_numbers
                self.mcq_start.current(0)
                self.mcq_end.current(len(mcq_numbers) - 1)
            else:
                self.mcq_start['values'] = []
                self.mcq_end['values'] = []
            
            if mcq_multi_count > 0:
                mcq_multi_numbers = self.exam_core.get_question_numbers('多选题')
                self.mcq_multi_start['values'] = mcq_multi_numbers
                self.mcq_multi_end['values'] = mcq_multi_numbers
                self.mcq_multi_start.current(0)
                self.mcq_multi_end.current(len(mcq_multi_numbers) - 1)
            else:
                self.mcq_multi_start['values'] = []
                self.mcq_multi_end['values'] = []
            
            self.status_var.set(f"系统版本: v{VERSION} | 题库加载成功: {judgment_count}道判断题, {mcq_count}道单选题, {mcq_multi_count}道多选题")
        except Exception as e:
            messagebox.showerror("错误", f"加载Excel文件失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 加载失败")
    
    def generate_preview(self):
        """生成试卷预览"""
        try:
            # 获取用户设置
            config = {
                'export_mode': self.export_mode.get(),
                'include_judgment': self.judgment_var.get(),
                'include_mcq': self.mcq_var.get(),
                'include_mcq_multi': self.mcq_multi_var.get(),
                'include_answers': self.answer_var.get(),
                'exam_title': self.exam_title.get(),
                'student_name': self.student_name.get(),
                'type_order': self.type_order.get(),
                'random_order': self.random_order_var.get(),
                'judgment_count': int(self.judgment_count.get()) if self.judgment_var.get() else 0,
                'mcq_count': int(self.mcq_count.get()) if self.mcq_var.get() else 0,
                'mcq_multi_count': int(self.mcq_multi_count.get()) if self.mcq_multi_var.get() else 0,
                'judgment_ratio': int(self.judgment_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'mcq_ratio': int(self.mcq_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'mcq_multi_ratio': int(self.mcq_multi_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'total_questions': int(self.total_questions_cb.get()) if self.export_mode.get() == "按比例导出" else 0,
                'judgment_start': int(self.judgment_start.get()) if self.judgment_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'judgment_end': int(self.judgment_end.get()) if self.judgment_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_start': int(self.mcq_start.get()) if self.mcq_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_end': int(self.mcq_end.get()) if self.mcq_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_multi_start': int(self.mcq_multi_start.get()) if self.mcq_multi_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_multi_end': int(self.mcq_multi_end.get()) if self.mcq_multi_var.get() and self.export_mode.get() == "顺序导出" else 0,
            }
            
            # 生成预览内容
            preview_content, total_count = self.exam_core.generate_preview(config)
            
            # 显示预览
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, preview_content)
            self.status_var.set(f"系统版本: v{VERSION} | 预览生成完成: 共{total_count}道题")
        except Exception as e:
            messagebox.showerror("错误", f"生成预览失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 生成预览失败")
    
    def export_word(self):
        """导出Word文档"""
        try:
            # 获取用户设置
            config = {
                'export_mode': self.export_mode.get(),
                'include_judgment': self.judgment_var.get(),
                'include_mcq': self.mcq_var.get(),
                'include_mcq_multi': self.mcq_multi_var.get(),
                'include_answers': self.answer_var.get(),
                'exam_title': self.exam_title.get(),
                'student_name': self.student_name.get(),
                'type_order': self.type_order.get(),
                'random_order': self.random_order_var.get(),
                'judgment_count': int(self.judgment_count.get()) if self.judgment_var.get() else 0,
                'mcq_count': int(self.mcq_count.get()) if self.mcq_var.get() else 0,
                'mcq_multi_count': int(self.mcq_multi_count.get()) if self.mcq_multi_var.get() else 0,
                'judgment_ratio': int(self.judgment_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'mcq_ratio': int(self.mcq_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'mcq_multi_ratio': int(self.mcq_multi_ratio.get().strip('%')) if self.export_mode.get() == "按比例导出" else 0,
                'total_questions': int(self.total_questions_cb.get()) if self.export_mode.get() == "按比例导出" else 0,
                'judgment_start': int(self.judgment_start.get()) if self.judgment_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'judgment_end': int(self.judgment_end.get()) if self.judgment_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_start': int(self.mcq_start.get()) if self.mcq_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_end': int(self.mcq_end.get()) if self.mcq_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_multi_start': int(self.mcq_multi_start.get()) if self.mcq_multi_var.get() and self.export_mode.get() == "顺序导出" else 0,
                'mcq_multi_end': int(self.mcq_multi_end.get()) if self.mcq_multi_var.get() and self.export_mode.get() == "顺序导出" else 0,
            }
            
            exam_count = int(self.exam_count.get())
            
            # 生成试卷数据
            exam_data = self.exam_core.generate_exam_data(config)
            
            # 导出Word
            export_to_word(exam_data, config, exam_count)
            
            self.status_var.set(f"系统版本: v{VERSION} | 已成功生成 {exam_count} 份试卷")
            messagebox.showinfo("成功", f"已成功生成 {exam_count} 份试卷")
        except Exception as e:
            messagebox.showerror("错误", f"导出Word失败:\n{str(e)}")
            self.status_var.set(f"系统版本: v{VERSION} | 导出失败")