"""
考试试卷生成系统 - 核心业务逻辑

功能：
1. 加载和处理Excel题库数据
2. 根据配置生成试卷内容
3. 管理题目数据和答案

接口：
- ExamCore: 核心业务逻辑类
  - load_excel(file_path): 加载Excel文件
  - get_question_type_count(question_type): 获取指定题型数量
  - get_question_numbers(question_type): 获取指定题型题号列表
  - generate_preview(config): 生成试卷预览内容
  - generate_exam_data(config): 生成试卷数据

依赖：
- pandas
"""

import pandas as pd
import random
import numpy as np
from collections import OrderedDict

class ExamCore:
    def __init__(self):
        self.exam_data = None
        self.excel_path = ""
    
    def load_excel(self, file_path):
        """加载Excel题库"""
        if not file_path:
            raise ValueError("请先选择Excel题库文件！")
        
        # 读取Excel文件
        self.exam_data = pd.read_excel(file_path)
        self.excel_path = file_path
        
        # 添加题号列
        self.exam_data['题号'] = range(1, len(self.exam_data) + 1)
        
        # 检查必要的列是否存在
        required_columns = ['题型', '题目', '正确答案']
        for col in required_columns:
            if col not in self.exam_data.columns:
                raise ValueError(f"Excel文件中缺少必需的列: '{col}'")
    
    def get_question_type_count(self, question_type):
        """获取指定题型数量"""
        if self.exam_data is None:
            return 0
        return len(self.exam_data[self.exam_data['题型'] == question_type])
    
    def get_question_numbers(self, question_type):
        """获取指定题型题号列表"""
        if self.exam_data is None:
            return []
        return list(self.exam_data[self.exam_data['题型'] == question_type]['题号'])
    
    def generate_preview(self, config):
        """生成试卷预览内容"""
        if self.exam_data is None:
            raise ValueError("请先加载题库！")
        
        # 验证设置
        if not (config['include_judgment'] or config['include_mcq'] or config['include_mcq_multi']):
            raise ValueError("请至少选择一种试题类型！")
        
        # 生成试卷数据
        exam_content, all_answers, total_count = self._generate_exam_content(config)
        
        # 添加答案部分
        if config['include_answers'] and all_answers:
            exam_content += "\n\n===== 参考答案 =====\n"
            
            # 按题号排序答案
            all_answers.sort(key=lambda x: x[0])
            answer_list = [ans[1] for ans in all_answers]
            answer_str = self._format_answers(answer_list)
            exam_content += f"全部答案: {answer_str}\n"
            
            # 按题型分组答案
            exam_content += "\n按题型分组答案:\n"
            judgment_answers = [ans[1] for ans in all_answers if ans[1] in ['√', '×']]
            if judgment_answers:
                exam_content += f"判断题答案: {self._format_answers(judgment_answers)}\n"
            
            mcq_answers = [ans[1] for ans in all_answers if ans[1] in ['A', 'B', 'C', 'D', 'E'] and len(ans[1]) == 1]
            if mcq_answers:
                exam_content += f"单选题答案: {self._format_answers(mcq_answers)}\n"
            
            # 添加多选题答案
            mcq_multi_answers = [ans[1] for ans in all_answers if len(ans[1]) > 1]
            if mcq_multi_answers:
                exam_content += f"多选题答案: {self._format_answers(mcq_multi_answers)}\n"
        
        return exam_content, total_count
    
    def generate_exam_data(self, config):
        """生成试卷数据用于导出Word"""
        if self.exam_data is None:
            raise ValueError("请先加载题库！")
        
        # 验证设置
        if not (config['include_judgment'] or config['include_mcq'] or config['include_mcq_multi']):
            raise ValueError("请至少选择一种试题类型！")
        
        # 生成试卷内容
        exam_content, all_answers, total_count = self._generate_exam_content(config)
        
        # 返回试卷数据
        return {
            'exam_title': config['exam_title'],
            'student_name': config['student_name'],
            'include_answers': config['include_answers'],
            'all_answers': all_answers,
            'total_count': total_count,
            'exam_content': exam_content  # 添加试卷内容
        }
    
    def _generate_exam_content(self, config):
        """生成试卷内容（内部方法）"""
        preview_content = f"试卷标题: {config['exam_title']}\n"
        preview_content += f"考生信息: {config['student_name']}\n\n"
        
        # 用于收集答案（按全局题号）
        all_answers = []
        question_counter = 1  # 全局题号计数器
        
        # 根据导出模式处理题目
        if config['export_mode'] == "随机抽取":
            sections = []
            if config['include_judgment']:
                sections.append(('判断题', config['judgment_count']))
            if config['include_mcq']:
                sections.append(('单选题', config['mcq_count']))
            if config['include_mcq_multi']:
                sections.append(('多选题', config['mcq_multi_count']))
            
            # 根据用户选择调整顺序
            if config['type_order'] == "单选题→判断题" and len(sections) > 1:
                sections.reverse()
            
            for section_type, section_count in sections:
                if section_type == '判断题':
                    # 判断题部分
                    preview_content += f"{question_counter}. 判断题（每题1分，共{section_count}分）\n\n"
                    judgment_questions = self.exam_data[self.exam_data["题型"] == "判断题"]
                    
                    if len(judgment_questions) < section_count:
                        section_count = len(judgment_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_judgment = judgment_questions.sample(section_count)
                    else:
                        selected_judgment = judgment_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_judgment.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} __________\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        if answer == "1":
                            answer = "√"
                        elif answer == "0":
                            answer = "×"
                        all_answers.append((question_counter, answer))
                        
                        question_counter += 1
                    
                    preview_content += "\n"
                
                elif section_type == '单选题':
                    # 单选题部分
                    preview_content += f"{question_counter}. 单选题（每题1分，共{section_count}分）\n\n"
                    mcq_questions = self.exam_data[self.exam_data["题型"] == "单选题"]
                    
                    if len(mcq_questions) < section_count:
                        section_count = len(mcq_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_mcq = mcq_questions.sample(section_count)
                    else:
                        selected_mcq = mcq_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_mcq.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [单选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
                
                elif section_type == '多选题':
                    # 多选题部分
                    preview_content += f"{question_counter}. 多选题（每题2分，共{section_count * 2}分）\n\n"
                    mcq_multi_questions = self.exam_data[self.exam_data["题型"] == "多选题"]
                    
                    if len(mcq_multi_questions) < section_count:
                        section_count = len(mcq_multi_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_mcq_multi = mcq_multi_questions.sample(section_count)
                    else:
                        selected_mcq_multi = mcq_multi_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_mcq_multi.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [多选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
        
        elif config['export_mode'] == "按比例导出":
            # 获取总题数
            total_count = config['total_questions']
            
            # 计算各题型数量
            judgment_count = max(1, int(total_count * config['judgment_ratio'] / 100))
            mcq_count = max(1, int(total_count * config['mcq_ratio'] / 100))
            mcq_multi_count = total_count - judgment_count - mcq_count
            
            sections = []
            if config['include_judgment']:
                sections.append(('判断题', judgment_count))
            if config['include_mcq']:
                sections.append(('单选题', mcq_count))
            if config['include_mcq_multi']:
                sections.append(('多选题', mcq_multi_count))
            
            # 根据用户选择调整顺序
            if config['type_order'] == "单选题→判断题" and len(sections) > 1:
                sections.reverse()
            
            for section_type, section_count in sections:
                if section_type == '判断题':
                    # 判断题部分
                    preview_content += f"{question_counter}. 判断题（每题1分，共{section_count}分）\n\n"
                    judgment_questions = self.exam_data[self.exam_data["题型"] == "判断题"]
                    
                    if len(judgment_questions) < section_count:
                        section_count = len(judgment_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_judgment = judgment_questions.sample(section_count)
                    else:
                        selected_judgment = judgment_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_judgment.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} __________\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        if answer == "1":
                            answer = "√"
                        elif answer == "0":
                            answer = "×"
                        all_answers.append((question_counter, answer))
                        
                        question_counter += 1
                    
                    preview_content += "\n"
                
                elif section_type == '单选题':
                    # 单选题部分
                    preview_content += f"{question_counter}. 单选题（每题1分，共{section_count}分）\n\n"
                    mcq_questions = self.exam_data[self.exam_data["题型"] == "单选题"]
                    
                    if len(mcq_questions) < section_count:
                        section_count = len(mcq_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_mcq = mcq_questions.sample(section_count)
                    else:
                        selected_mcq = mcq_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_mcq.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [单选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
                
                elif section_type == '多选题':
                    # 多选题部分
                    preview_content += f"{question_counter}. 多选题（每题2分，共{section_count * 2}分）\n\n"
                    mcq_multi_questions = self.exam_data[self.exam_data["题型"] == "多选题"]
                    
                    if len(mcq_multi_questions) < section_count:
                        section_count = len(mcq_multi_questions)
                    
                    # 抽取题目
                    if config['random_order']:
                        selected_mcq_multi = mcq_multi_questions.sample(section_count)
                    else:
                        selected_mcq_multi = mcq_multi_questions.head(section_count)
                    
                    # 添加题目
                    for _, row in selected_mcq_multi.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [多选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
        
        elif config['export_mode'] == "顺序导出":
            # 获取题目范围
            judgment_start = config['judgment_start']
            judgment_end = config['judgment_end']
            mcq_start = config['mcq_start']
            mcq_end = config['mcq_end']
            mcq_multi_start = config['mcq_multi_start']
            mcq_multi_end = config['mcq_multi_end']
            
            # 验证范围
            if config['include_judgment'] and judgment_start > judgment_end:
                raise ValueError("判断题起始题号不能大于结束题号！")
            
            if config['include_mcq'] and mcq_start > mcq_end:
                raise ValueError("单选题起始题号不能大于结束题号！")
            
            if config['include_mcq_multi'] and mcq_multi_start > mcq_multi_end:
                raise ValueError("多选题起始题号不能大于结束题号！")
            
            sections = []
            if config['include_judgment']:
                judgment_count = judgment_end - judgment_start + 1
                sections.append(('判断题', judgment_count, judgment_start, judgment_end))
            
            if config['include_mcq']:
                mcq_count = mcq_end - mcq_start + 1
                sections.append(('单选题', mcq_count, mcq_start, mcq_end))
            
            if config['include_mcq_multi']:
                mcq_multi_count = mcq_multi_end - mcq_multi_start + 1
                sections.append(('多选题', mcq_multi_count, mcq_multi_start, mcq_multi_end))
            
            # 根据用户选择调整顺序
            if config['type_order'] == "单选题→判断题" and len(sections) > 1:
                sections.reverse()
            
            for section in sections:
                section_type = section[0]
                section_count = section[1]
                start_num = section[2]
                end_num = section[3]
                
                if section_type == '判断题':
                    # 判断题部分
                    preview_content += f"{question_counter}. 判断题（每题1分，共{section_count}分）\n\n"
                    judgment_questions = self.exam_data[
                        (self.exam_data["题型"] == "判断题") & 
                        (self.exam_data['题号'] >= start_num) & 
                        (self.exam_data['题号'] <= end_num)
                    ]
                    
                    # 按题号排序
                    judgment_questions = judgment_questions.sort_values('题号')
                    
                    for _, row in judgment_questions.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} __________\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        if answer == "1":
                            answer = "√"
                        elif answer == "0":
                            answer = "×"
                        all_answers.append((question_counter, answer))
                        
                        question_counter += 1
                    
                    preview_content += "\n"
                
                elif section_type == '单选题':
                    # 单选题部分
                    preview_content += f"{question_counter}. 单选题（每题1分，共{section_count}分）\n\n"
                    mcq_questions = self.exam_data[
                        (self.exam_data["题型"] == "单选题") & 
                        (self.exam_data['题号'] >= start_num) & 
                        (self.exam_data['题号'] <= end_num)
                    ]
                    
                    # 按题号排序
                    mcq_questions = mcq_questions.sort_values('题号')
                    
                    for _, row in mcq_questions.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [单选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
                
                elif section_type == '多选题':
                    # 多选题部分
                    preview_content += f"{question_counter}. 多选题（每题2分，共{section_count * 2}分）\n\n"
                    mcq_multi_questions = self.exam_data[
                        (self.exam_data["题型"] == "多选题") & 
                        (self.exam_data['题号'] >= start_num) & 
                        (self.exam_data['题号'] <= end_num)
                    ]
                    
                    # 按题号排序
                    mcq_multi_questions = mcq_multi_questions.sort_values('题号')
                    
                    for _, row in mcq_multi_questions.iterrows():
                        preview_content += f"{question_counter}. {row['题目']} [多选题]\n"
                        
                        # 添加选项
                        options = []
                        for option in ['A', 'B', 'C', 'D', 'E']:
                            option_col = f"选项{option}"
                            if option_col in row and pd.notna(row[option_col]) and row[option_col].strip():
                                # 清理选项格式
                                option_text = row[option_col].strip()
                                if option_text.startswith('[') and option_text[1:2].isalpha() and option_text[2:3] == ']':
                                    option_text = option_text[3:].strip()
                                options.append(f"{option}. {option_text}")
                        
                        preview_content += "   " + "    ".join(options) + "\n\n"
                        
                        # 确保答案是字符串
                        answer = str(row['正确答案']).strip()
                        all_answers.append((question_counter, answer))
                        question_counter += 1
        
        return preview_content, all_answers, question_counter - 1
    
    def _format_answers(self, answers):
        """格式化答案字符串为1-5:ABCDA格式"""
        if not answers:
            return ""
        
        # 确保所有答案都是字符串
        answers = [str(ans) for ans in answers]
        
        # 每5个答案一组
        groups = []
        for i in range(0, len(answers), 5):
            group_start = i + 1
            group_end = min(i + 5, len(answers))
            group_answers = "".join(answers[i:i+5])
            groups.append(f"{group_start}-{group_end}: {group_answers}")
        
        return "  ".join(groups)