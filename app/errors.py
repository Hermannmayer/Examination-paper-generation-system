"""领域错误。

业务层不弹对话框，而是抛出带错误码的 :class:`DomainError`；
界面层（``ui/api.py``）统一捕获并转成前端可渲染的 JSON 信封。
"""


class Codes:
    """错误码。前端按 code 决定展示方式，message 仅作兜底。"""

    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    MISSING_COLUMNS = "MISSING_COLUMNS"
    EMPTY_SHEET = "EMPTY_SHEET"
    NOT_LOADED = "NOT_LOADED"
    NO_TYPE_SELECTED = "NO_TYPE_SELECTED"
    INSUFFICIENT_QUESTIONS = "INSUFFICIENT_QUESTIONS"
    EMPTY_SEQUENTIAL_RANGE = "EMPTY_SEQUENTIAL_RANGE"
    INVALID_RANGE = "INVALID_RANGE"
    RATIO_SUM_NOT_100 = "RATIO_SUM_NOT_100"
    DIFFICULTY_COLUMN_MISSING = "DIFFICULTY_COLUMN_MISSING"
    POOL_EXHAUSTED = "POOL_EXHAUSTED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    FONT_NOT_FOUND = "FONT_NOT_FOUND"
    INTERNAL = "INTERNAL"

    # 以下为信息型（配合 warning 使用，通常不作为异常抛出）
    REUSED_QUESTIONS = "REUSED_QUESTIONS"
    DIFFICULTY_WEIGHTS_NORMALIZED = "DIFFICULTY_WEIGHTS_NORMALIZED"

    # 文案：中文提示，前端可直接展示
    MESSAGES = {
        FILE_NOT_FOUND: "找不到文件",
        UNSUPPORTED_FORMAT: "不支持的文件格式",
        MISSING_COLUMNS: "题库缺少必需的列",
        EMPTY_SHEET: "题库为空",
        NOT_LOADED: "请先加载题库",
        NO_TYPE_SELECTED: "请至少选择一种题型",
        INSUFFICIENT_QUESTIONS: "题库题量不足",
        EMPTY_SEQUENTIAL_RANGE: "顺序导出未填写题目范围",
        INVALID_RANGE: "题目范围不合法",
        RATIO_SUM_NOT_100: "各题型比例合计不等于 100%",
        DIFFICULTY_COLUMN_MISSING: "题库缺少难度列",
        POOL_EXHAUSTED: "题库已被抽完",
        CANCELLED_BY_USER: "操作已取消",
        FONT_NOT_FOUND: "系统中找不到可用的中文字体",
        INTERNAL: "程序内部错误",
    }


class DomainError(Exception):
    """可预期的业务错误。

    参数:
        code: 见 :class:`Codes`
        message: 面向用户的中文描述（可直接展示）
        hint: 可选的下一步建议
        details: 结构化补充信息，需保证 JSON 可序列化
    """

    def __init__(self, code, message=None, hint="", details=None):
        self.code = code
        self.message = message or Codes.MESSAGES.get(code, code)
        self.hint = hint
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
        }

    def __repr__(self):
        return f"DomainError({self.code!r}, {self.message!r})"


class CancelledByUser(DomainError):
    """用户在长任务中途取消。"""

    def __init__(self, message=None):
        super().__init__(Codes.CANCELLED_BY_USER, message)
