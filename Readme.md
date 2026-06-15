# 考试试卷生成系统

基于 Python + Tkinter 的桌面应用程序，从 Excel 题库抽取题目生成试卷并导出为 Word 文档。

## 快速开始

### 下载即用
从 [Releases](https://github.com/Hermannmayer/Examination-paper-generation-system/releases) 下载 `exam-generator.exe`，双击运行。

### 源码运行

```bash
git clone https://github.com/Hermannmayer/Examination-paper-generation-system.git
cd Examination-paper-generation-system
pip install pandas python-docx openpyxl
python main.py
```

## 功能特性

### 题型管理
- 三种题型：判断题、单选题、多选题
- **动态排序** — ↑↓ 按钮调整题型顺序
- **每题独立分数** — 每种题型可单独设置分值（1-20 分）
- 自动计算总分并显示

### 导出模式
| 模式 | 说明 |
|------|------|
| 随机抽取 | 从题库随机抽指定数量的题 |
| 按比例导出 | 按百分比分配各题型题数（自动补全尾数） |
| 顺序导出 | 按该题型内的序号范围选取 |

### 试卷配置
- 试卷标题、考生信息、考试时间
- 纸张尺寸（A4 / A3 / B5 / Letter）
- 可配置页眉文字
- 题目随机排序开关
- 包含/不包含参考答案
- **模板保存/加载** — 配置存为 JSON，一键恢复

### 预览与导出
- 实时预览（支持**自动刷新**，800ms 防抖）
- Word 导出排版优化：题号加粗、考生信息居中、行间距 1.15
- **多份试卷去重** — 生成多份时题目不重复

### 参考答案
- 按题型分组显示
- 多选题用方括号包裹：`[ABD]`
- 每 5 题一组：`1-5: A B C D E`

## 项目结构

```
main.py             # 程序入口
gui.py              # Tkinter 图形界面
core.py             # 核心业务逻辑
docx_utils.py       # Word 文档导出
config.py           # 配置常量
requirements.txt    # Python 依赖
题库模板.xlsx       # 示例题库
venv.bat            # 一键进入虚拟环境
```

## Excel 题库格式

| 列名 | 描述 | 示例 |
|------|------|------|
| 题型 | 题目类型 | 判断题 / 单选题 / 多选题 |
| 题目 | 题目内容 | 养老护理的基本原则是... |
| 正确答案 | 题目答案 | √ / A / ABD |
| 选项A | 单选题选项 | 安全第一 |
| 选项B | 单选题选项 | 以人为本 |
| 选项C | 单选题选项 | 追求利润 |
| 选项D | 单选题选项 | 效率优先 |

- 必须包含 **题型**、**题目**、**正确答案** 三列
- 判断题答案：`1` = √, `0` = ×
- 多选题答案：`ABD`（无分隔符）

## 使用流程

1. 启动程序 — 点击「模板」加载示例，或「浏览」选择自己的 Excel
2. 点击「加载题库」读取题目
3. 左侧面板配置试卷参数
4. 勾选「自动刷新预览」实时查看，或点击「生成预览」
5. 满意后点击「导出 Word」
6. 可将当前配置保存为模板

## 技术栈

Python 3.7+ · Tkinter · pandas · openpyxl · python-docx · PyInstaller

## 许可证

MIT
