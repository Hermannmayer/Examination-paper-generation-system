"""
考试试卷生成系统 - 核心业务逻辑
"""

import pandas as pd


def _clean_option_text(text):
    """清理选项文本：去除 [A] 前缀"""
    t = str(text).strip()
    if t.startswith('[') and len(t) > 2 and t[1:2].isalpha() and t[2:3] == ']':
        return t[3:].strip()
    return t


def _normalize_answer(answer, question_type="判断题"):
    """标准化答案格式：判断题 1→√, 0→×"""
    a = str(answer).strip()
    if question_type == "判断题":
        if a == "1":
            return "√"
        if a == "0":
            return "×"
    return a


def _format_answers(answers):
    """格式化答案字符串为分组格式（支持多选题多字符答案）"""
    if not answers:
        return ""
    answers = [str(a) for a in answers]
    # 多选题答案（如 "ABD"）用方括号包裹便于区分
    processed = [f'[{a}]' if len(a) > 1 else a for a in answers]
    groups = []
    for i in range(0, len(processed), 5):
        start = i + 1
        end = min(i + 5, len(processed))
        groups.append(f"{start}-{end}: {' '.join(processed[i:i+5])}")
    return "  ".join(groups)


def _type_key(q_type):
    """题型名称到配置键前缀的映射"""
    return {"判断题": "judgment", "单选题": "mcq", "多选题": "mcq_multi"}.get(q_type, q_type)


def _get_section_count(q_type, config):
    """获取某题型的抽取数量"""
    key = f'{_type_key(q_type)}_count'
    try:
        return int(config.get(key, 0))
    except (ValueError, TypeError):
        return 0


def _pick_questions(df, q_type, mode_config, exclude=None):
    """根据模式和配置抽取题目

    参数:
        df: 完整题库 DataFrame
        q_type: 题型名称
        mode_config: 配置字典
        exclude: 已使用的 (q_type, index) 集合（多份试卷去重）

    返回:
        筛选后的 DataFrame
    """
    questions = df[df["题型"] == q_type].copy()
    if questions.empty:
        return questions

    mode = mode_config.get('export_mode', '随机抽取')

    if mode == "顺序导出":
        key = _type_key(q_type)
        start = mode_config.get(f'{key}_start', 1)
        end = mode_config.get(f'{key}_end', len(questions))
        # start/end 是指该题型内的第 N 题（1-based）
        idx_start = max(0, start - 1)
        idx_end = min(len(questions), end)
        if idx_start < idx_end:
            questions = questions.iloc[idx_start:idx_end]
        else:
            questions = questions.iloc[:0]
        # 顺序导出不随机
    else:
        count = _get_section_count(q_type, mode_config)
        # 排除已用的题
        if exclude and len(exclude) > 0:
            mask = ~questions.index.isin(exclude)
            questions = questions[mask]

        if count > 0 and count < len(questions):
            if mode_config.get('random_order', True):
                questions = questions.sample(n=count)
            else:
                questions = questions.head(count)

    return questions


def _render_question(q_num, row, q_type):
    """生成单题文本和答案

    返回:
        (question_text, answer, q_type)
    """
    answer = _normalize_answer(row['正确答案'], q_type)

    if q_type == "判断题":
        text = f"{q_num}. {row['题目']} __________\n"
    else:
        text = f"{q_num}. {row['题目']} [{q_type}]\n"
        options = []
        for opt in ['A', 'B', 'C', 'D', 'E']:
            col = f"选项{opt}"
            if col in row and pd.notna(row[col]) and str(row[col]).strip():
                options.append(f"{opt}. {_clean_option_text(row[col])}")
        if options:
            text += "   " + "    ".join(options) + "\n"
        else:
            text += "\n"

    return text, answer, q_type


def _distribute_ratios(total, ratios):
    """按比例分配题数，补全尾数

    参数:
        total: 总题数
        ratios: [(type_name, ratio_percent), ...]

    返回:
        [(type_name, count), ...]
    """
    if not ratios:
        return []

    result = []
    allocated = 0
    for name, ratio in ratios:
        count = int(total * ratio / 100)
        result.append((name, count))
        allocated += count

    # 补全尾数给比例最大的题型
    remainder = total - allocated
    if remainder > 0:
        max_idx = max(range(len(ratios)), key=lambda i: ratios[i][1])
        name, count = result[max_idx]
        result[max_idx] = (name, count + remainder)

    return result


class ExamCore:
    def __init__(self):
        self.exam_data = None
        self.excel_path = ""

    def load_excel(self, file_path):
        """加载Excel题库"""
        if not file_path:
            raise ValueError("请先选择Excel题库文件！")
        self.exam_data = pd.read_excel(file_path)
        self.excel_path = file_path
        self.exam_data['题号'] = range(1, len(self.exam_data) + 1)
        for col in ['题型', '题目', '正确答案']:
            if col not in self.exam_data.columns:
                raise ValueError(f"Excel文件中缺少必需的列: '{col}'")

    def get_question_type_count(self, question_type):
        if self.exam_data is None:
            return 0
        return len(self.exam_data[self.exam_data['题型'] == question_type])

    def get_question_numbers(self, question_type):
        """获取该题型在 DataFrame 中的序号列表（1-based）"""
        if self.exam_data is None:
            return []
        q = self.exam_data[self.exam_data['题型'] == question_type]
        return list(range(1, len(q) + 1))  # 题型内序号，不是全局行号

    def _build_sections(self, config):
        """构建题型列表（支持 question_order 动态排序）"""
        order = config.get('question_order')
        if order:
            raw = []
            for key in order:
                name = {"judgment": "判断题", "mcq": "单选题", "mcq_multi": "多选题"}.get(key, key)
                if config.get(f'include_{key}', False):
                    raw.append((name, key))
        else:
            raw = []
            if config.get('include_judgment'):
                raw.append(('判断题', 'judgment'))
            if config.get('include_mcq'):
                raw.append(('单选题', 'mcq'))
            if config.get('include_mcq_multi'):
                raw.append(('多选题', 'mcq_multi'))
            if config.get('type_order') == "单选题→判断题" and len(raw) > 1:
                raw.reverse()

        mode = config.get('export_mode', '随机抽取')

        if mode == "按比例导出":
            total = int(config.get('total_questions', 100))
            ratios = [(name, int(config.get(f'{key}_ratio', 0))) for name, key in raw]
            return [(name, cnt) for name, cnt in _distribute_ratios(total, ratios) if cnt > 0]
        else:
            return [(name, _get_section_count(name, config)) for name, _ in raw if _get_section_count(name, config) > 0]

    def _generate_exam_content(self, config, exclude=None):
        """生成一份试卷内容

        参数:
            config: 配置字典
            exclude: 已用题目标识集合，每项为 (题型, df_index)

        返回:
            (content_text, [(q_num, answer, q_type), ...], total_count, used_set)
        """
        content = f"试卷标题: {config['exam_title']}\n"
        content += f"考生信息: {config['student_name']}\n\n"
        if config.get('exam_time'):
            content += f"考试时间: {config['exam_time']} 分钟\n\n"

        all_answers = []
        q_num = 1
        used = set()

        for section_type, count in self._build_sections(config):
            key = {"判断题": "judgment", "单选题": "mcq", "多选题": "mcq_multi"}.get(section_type, "judgment")
            score = int(config.get(f'{key}_score', 1))
            content += f"    {section_type}（每题{score}分，共{count * score}分）\n\n"

            questions = _pick_questions(self.exam_data, section_type, config, exclude)
            if len(questions) < count:
                count = len(questions)

            for idx in range(count):
                row = questions.iloc[idx]
                q_text, answer, qtype = _render_question(q_num, row, section_type)
                content += q_text
                all_answers.append((q_num, answer, qtype))
                used.add((section_type, row.name))
                q_num += 1

            content += "\n"

        return content, all_answers, q_num - 1, used

    def _build_answer_section(self, all_answers):
        """构建参考答案文本"""
        if not all_answers:
            return ""

        result = "\n===== 参考答案 =====\n"
        sorted_ans = sorted(all_answers, key=lambda x: x[0])

        # 全部答案
        result += f"全部答案: {_format_answers([a[1] for a in sorted_ans])}\n"

        # 按题型分组（用元数据，不靠答案值猜测）
        result += "\n按题型分组答案:\n"
        j_ans = [a[1] for a in sorted_ans if a[2] == "判断题"]
        if j_ans:
            result += f"判断题答案: {_format_answers(j_ans)}\n"
        m_ans = [a[1] for a in sorted_ans if a[2] == "单选题"]
        if m_ans:
            result += f"单选题答案: {_format_answers(m_ans)}\n"
        mm_ans = [a[1] for a in sorted_ans if a[2] == "多选题"]
        if mm_ans:
            result += f"多选题答案: {_format_answers(mm_ans)}\n"

        return result

    def generate_preview(self, config):
        """生成一份试卷的预览"""
        if self.exam_data is None:
            raise ValueError("请先加载题库！")
        if not (config.get('include_judgment') or config.get('include_mcq') or config.get('include_mcq_multi')):
            raise ValueError("请至少选择一种试题类型！")

        content, all_answers, total_count, _ = self._generate_exam_content(config)

        if config.get('include_answers'):
            content += self._build_answer_section(all_answers)

        return content, total_count

    def generate_exam_datas(self, config, exam_count=1):
        """生成多份试卷数据，各卷题目不重复

        返回:
            [exam_data_dict, ...]
        """
        if self.exam_data is None:
            raise ValueError("请先加载题库！")
        if not (config.get('include_judgment') or config.get('include_mcq') or config.get('include_mcq_multi')):
            raise ValueError("请至少选择一种试题类型！")

        global_exclude = set()  # 跨试卷去重
        results = []

        for i in range(exam_count):
            content, all_answers, total_count, used = self._generate_exam_content(
                config, exclude=global_exclude
            )
            global_exclude |= used  # 累加已用的题

            results.append({
                'exam_title': config['exam_title'],
                'student_name': config['student_name'],
                'exam_time': config.get('exam_time', ''),
                'include_answers': config.get('include_answers', False),
                'all_answers': all_answers,
                'total_count': total_count,
                'exam_content': content,
                'exam_number': i + 1,
            })

        return results
