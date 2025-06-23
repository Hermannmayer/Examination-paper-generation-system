"""
考试试卷生成系统 - Word文档处理工具

功能：
1. 创建和格式化Word文档
2. 添加试卷内容到Word文档
3. 导出试卷到Word文件

接口：
- export_to_word(exam_data, config, exam_count=1): 导出试卷到Word文件

依赖：
- python-docx
"""

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
import os
from tkinter import filedialog

def export_to_word(exam_data, config, exam_count=1):
    """
    导出试卷到Word文件
    
    参数：
    exam_data: 试卷数据字典
    config: 用户配置字典
    exam_count: 生成试卷份数
    """
    # 生成多份试卷
    output_path = ""
    for exam_num in range(1, exam_count + 1):
        # 创建Word文档
        doc = Document()
        
        # 设置中文字体
        doc.styles['Normal'].font.name = u'宋体'
        doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), u'宋体')
        doc.styles['Normal'].font.size = Pt(10.5)
        
        # 添加标题
        title_text = f"{exam_data['exam_title']} (试卷{exam_num})" if exam_count > 1 else exam_data['exam_title']
        title = doc.add_heading(title_text, level=0)
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        title_run = title.runs[0]
        title_run.font.size = Pt(16)
        title_run.font.bold = True
        
        # 添加考生信息
        info_para = doc.add_paragraph()
        info_para.add_run(exam_data['student_name'])
        info_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        
        doc.add_paragraph()
        
        # 添加试卷内容
        content_para = doc.add_paragraph()
        content_para.add_run(exam_data['exam_content'])
        
        # 添加分页符
        doc.add_page_break()
        
        # 添加答案页（如果需要）
        if exam_data['include_answers'] and exam_data['all_answers']:
            answer_heading = doc.add_heading("参考答案", level=1)
            answer_heading.runs[0].font.size = Pt(14)
            
            # 按题号排序答案
            all_answers = sorted(exam_data['all_answers'], key=lambda x: x[0])
            
            # 添加全部答案
            p_all = doc.add_paragraph()
            p_all.add_run("全部答案: ")
            
            # 提取答案字符串
            answer_list = [ans[1] for ans in all_answers]
            p_all.add_run(_format_answers(answer_list))
            p_all.paragraph_format.space_after = Pt(12)
            
            # 按题型分组答案
            judgment_answers = [ans[1] for ans in all_answers if ans[1] in ['√', '×']]
            if judgment_answers:
                p_judgment = doc.add_paragraph()
                p_judgment.add_run("判断题答案: ")
                p_judgment.add_run(_format_answers(judgment_answers))
                p_judgment.paragraph_format.space_after = Pt(12)
            
            mcq_answers = [ans[1] for ans in all_answers if ans[1] in ['A', 'B', 'C', 'D', 'E'] and len(ans[1]) == 1]
            if mcq_answers:
                p_mcq = doc.add_paragraph()
                p_mcq.add_run("单选题答案: ")
                p_mcq.add_run(_format_answers(mcq_answers))
                p_mcq.paragraph_format.space_after = Pt(12)
            
            # 添加多选题答案
            mcq_multi_answers = [ans[1] for ans in all_answers if len(ans[1]) > 1]
            if mcq_multi_answers:
                p_mcq_multi = doc.add_paragraph()
                p_mcq_multi.add_run("多选题答案: ")
                p_mcq_multi.add_run(_format_answers(mcq_multi_answers))
                p_mcq_multi.paragraph_format.space_after = Pt(12)
        
        # 保存文档
        if exam_count > 1 or exam_num == 1:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".docx",
                filetypes=[("Word文档", "*.docx")],
                initialfile=f"试卷_{exam_num}.docx"
            )
        
        if not output_path:
            return
        
        doc.save(output_path)

def _format_answers(answers):
    """格式化答案字符串为1-5:ABCDA格式（内部函数）"""
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