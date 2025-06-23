# 考试试卷生成系统文档

## 系统概述
考试试卷生成系统是一个基于Python的桌面应用程序，用于从Excel题库中抽取题目生成试卷并导出为Word文档。系统支持多种导出模式和题型配置，特别适合教育机构和培训机构使用。

### 核心功能
- **题库管理**：加载Excel格式的题库文件
- **试卷配置**：
  - 设置试卷标题和考生信息
  - 选择导出模式（随机抽取、按比例导出、顺序导出）
  - 配置题型（判断题/单选题）和数量
  - 设置题型顺序和题目随机排序
  - 选择是否包含答案
- **预览功能**：实时预览生成的试卷内容
- **导出功能**：将试卷导出为Word文档（支持多份试卷生成）
- **版本管理**：显示系统版本号，便于追踪和管理


### 系统架构
```
exam_generator/
├── main.py             # 程序入口
├── gui.py              # 图形用户界面
├── core.py             # 核心业务逻辑
├── docx_utils.py       # Word文档处理
└── config.py           # 配置常量
```

## 模块接口说明

### 1. main.py
**功能**：程序入口点

```python
from gui import ExamGeneratorGUI
import tkinter as tk

def main():
    root = tk.Tk()
    app = ExamGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
```

### 2. gui.py
**功能**：图形用户界面实现

#### 主要类：`ExamGeneratorGUI`
```python
class ExamGeneratorGUI:
    def __init__(self, root):
        """初始化GUI界面"""
    
    def browse_file(self):
        """浏览Excel文件"""
    
    def load_excel(self):
        """加载Excel题库"""
    
    def generate_preview(self):
        """生成试卷预览"""
    
    def export_word(self):
        """导出Word文档"""
    
    def on_export_mode_change(self, event):
        """处理导出模式变更事件"""
```

### 3. core.py
**功能**：核心业务逻辑处理

#### 主要类：`ExamCore`
```python
class ExamCore:
    def __init__(self):
        """初始化核心组件"""
    
    def load_excel(self, file_path):
        """加载Excel题库文件"""
    
    def get_question_type_count(self, question_type):
        """获取指定题型数量"""
    
    def get_question_numbers(self, question_type):
        """获取指定题型题号列表"""
    
    def generate_preview(self, config):
        """生成试卷预览内容"""
    
    def generate_exam_data(self, config):
        """生成试卷数据（用于导出Word）"""
    
    def _generate_exam_content(self, config):
        """内部方法：生成试卷内容"""
    
    def _format_answers(self, answers):
        """格式化答案字符串"""
```

### 4. docx_utils.py
**功能**：Word文档导出处理

```python
def export_to_word(exam_data, config, exam_count=1):
    """
    导出试卷到Word文件
    
    参数：
    - exam_data: 试卷数据字典
    - config: 用户配置字典
    - exam_count: 生成试卷份数
    """
    
def _format_answers(answers):
    """内部函数：格式化答案字符串"""
```

### 5. config.py
**功能**：系统常量配置

```python
# 默认试卷标题
DEFAULT_EXAM_TITLE = "考试试卷"

# 默认考生信息
DEFAULT_STUDENT_INFO = "姓名：__________  考号：__________"
```

## 使用流程
1. **启动程序**：运行`main.py`
2. **加载题库**：通过GUI界面选择Excel题库文件
3. **配置试卷**：
   - 设置试卷标题和考生信息
   - 选择导出模式（随机/比例/顺序）
   - 配置题型和数量
   - 设置其他选项（包含答案、随机排序等）
4. **预览试卷**：点击"生成预览"查看试卷内容
5. **导出Word**：点击"导出Word"保存试卷文档

## 技术依赖
- **Python 3.7+**
- **必需库**：
  - `pandas` (处理Excel数据)
  - `python-docx` (生成Word文档)
  - `tkinter` (GUI界面)
  - `openpyxl` (Excel文件支持)

安装依赖：
```bash
pip install pandas python-docx openpyxl
```

## Excel题库格式要求
| 列名     | 描述                     | 示例              |
|----------|--------------------------|-------------------|
| 题型     | 题目类型（判断题/单选题）| "判断题"          |
| 题目     | 题目内容                 | "养老护理的基本原则是..." |
| 正确答案 | 题目答案                 | "√" 或 "A"       |
| 选项A-D  | 单选题选项(可选)         | "安全第一"        |

## 系统特点
1. **灵活配置**：支持三种导出模式和多种题型配置
2. **批量生成**：一次可生成多份不同试卷
3. **答案管理**：可生成按题型分组的参考答案
4. **用户友好**：直观的GUI界面和实时预览功能
5. **高效处理**：支持大型题库文件处理

## 使用场景
- 职业资格考试试卷生成
- 学校期末考试组卷
- 培训机构练习题库
- 在线教育平台试卷导出
  
##目前存在的问题：
  1.顺序导出功能未达到预期
  2.批量导出试卷功能出现了意外的适用范围
  
## 注意事项
1. Excel文件必须包含"题型"、"题目"和"正确答案"三列
2. 单选题需要提供选项列（选项A、选项B等）
3. 判断题正确答案应为"1"(√)或"0"(×)
4. 导出Word前建议先预览内容

## TODO：
1. 添加各题型排序功能
2. 修复顺序生成题目未按照预期选择题目的bug
3. 支持更多题型
4. 发行gui打包版本exe