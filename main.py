"""
考试试卷生成系统 - 主程序入口

功能：
1. 创建主窗口
2. 初始化应用程序
3. 启动主事件循环

依赖：
- gui.ExamGeneratorGUI
"""

from gui import ExamGeneratorGUI
import tkinter as tk
from config import VERSION

def main():
    root = tk.Tk()
    app = ExamGeneratorGUI(root)
    
    # 控制台打印版本信息
    print(f"考试试卷生成系统 v{VERSION}")
    print("Copyright © 2023 考试系统开发团队")
    
    root.mainloop()

if __name__ == "__main__":
    main()