"""全局常量。

题型注册表由旧 Tkinter 界面迁移而来，字段名保持不变，
以便已有 JSON 模板与旧配置键继续可用。
"""

# 版本号：1.0.0 对应分屏界面重构 + pandas 移除 + 9 个 bug 修复
VERSION = "1.0.0"

DEFAULT_EXAM_TITLE = "（）考试试卷"
DEFAULT_STUDENT_INFO = "姓名：__________  考号：__________"

# 题型注册表：加新题型只需在此加一行
QUESTION_TYPES = [
    {"key": "judgment", "label": "判断题", "score": 1, "default": 1},
    {"key": "mcq", "label": "单选题", "score": 1, "default": 1},
    {"key": "mcq_multi", "label": "多选题", "score": 2, "default": 0},
    {"key": "short_answer", "label": "简答题", "score": 5, "default": 0},
]

TYPE_BY_KEY = {qt["key"]: qt for qt in QUESTION_TYPES}
LABEL_BY_KEY = {qt["key"]: qt["label"] for qt in QUESTION_TYPES}
KEY_BY_LABEL = {qt["label"]: qt["key"] for qt in QUESTION_TYPES}
ALL_LABELS = [qt["label"] for qt in QUESTION_TYPES]

# 客观题：答案是 A/√/ABD 这种短标记，答案页可以按题号压成一行一行的紧凑格式。
# 简答题的答案是成段文字，必须单独排版。
OBJECTIVE_LABELS = ["判断题", "单选题", "多选题"]
ESSAY_LABELS = ["简答题"]

# 简答题在试卷上留几行作答横线
ESSAY_BLANK_LINES = 3

# 简答题在答题卡上留几行。答题卡要尽量压在一页内，所以比试卷少一行。
ESSAY_CARD_LINES = 2

# 题库必需列。其余「选项A..E」为可选列。
REQUIRED_COLUMNS = ["题型", "题目", "正确答案"]
OPTION_LETTERS = ["A", "B", "C", "D", "E"]

# 纸张尺寸（宽, 高，单位 mm）
PAPER_SIZES = {
    "A4": (210, 297),
    "A3": (297, 420),
    "B5": (176, 250),
    "Letter": (216, 279),
}

EXPORT_MODE_RANDOM = "随机抽取"
EXPORT_MODE_RATIO = "按比例导出"
EXPORT_MODE_SEQUENTIAL = "顺序导出"
EXPORT_MODES = [EXPORT_MODE_RANDOM, EXPORT_MODE_RATIO, EXPORT_MODE_SEQUENTIAL]

# 题库耗尽时的处理策略
POOL_WARN_AND_REUSE = "warn_and_reuse"
POOL_SHRINK = "shrink"
POOL_ERROR = "error"
POOL_STRATEGIES = [POOL_WARN_AND_REUSE, POOL_SHRINK, POOL_ERROR]
