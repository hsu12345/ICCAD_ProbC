"""
生成清華大學資訊工程系專題報告模板
使用 python-docx 庫生成符合格式要求的 Word 文檔
"""

from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from datetime import datetime

def create_report_template():
    """創建符合格式要求的專題報告模板"""
    
    # 創建文檔
    doc = Document()
    
    # 設置頁面大小為 A4
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    
    # 設置邊界：上邊界及下邊界：2.54cm，左邊界及右邊界：3.17cm
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.17)
    section.right_margin = Cm(3.17)
    
    # 設置頁碼（需要在頁腳添加）
    footer = section.footer
    footer_para = footer.paragraphs[0]
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 標題頁
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run('國立清華大學資訊工程系 ___學年度__學期專題報告')
    title_run.font.name = '新細明體'
    title_run.font.size = Pt(14)
    title_run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    # 添加空行
    doc.add_paragraph()
    doc.add_paragraph()
    
    # 根據官方格式創建封面表格
    # 第一個表格：專題名稱和競賽資訊
    table1 = doc.add_table(rows=2, cols=4)
    table1.style = 'Table Grid'
    
    # 第一行：專題名稱
    row1_cells = table1.rows[0].cells
    cell_0_0 = row1_cells[0].merge(row1_cells[3])  # 合併4個單元格
    para = cell_0_0.paragraphs[0]
    run = para.add_run('專題名稱')
    run.font.name = '新細明體'
    run.font.size = Pt(12)
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    run.bold = True
    
    # 第二行：參加競賽或計畫
    row2_cells = table1.rows[1].cells
    para1 = row2_cells[0].paragraphs[0]
    run1 = para1.add_run('參加競賽或計畫')
    run1.font.name = '新細明體'
    run1.font.size = Pt(12)
    run1._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    run1.bold = True
    
    para2 = row2_cells[1].paragraphs[0]
    run2 = para2.add_run('☐ 參加對外競賽')
    run2.font.name = '新細明體'
    run2.font.size = Pt(12)
    run2._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    para3 = row2_cells[2].paragraphs[0]
    run3 = para3.add_run('☐ 參與其他計畫')
    run3.font.name = '新細明體'
    run3.font.size = Pt(12)
    run3._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    para4 = row2_cells[3].paragraphs[0]
    run4 = para4.add_run('☐ 無參加對外競賽或任何計畫')
    run4.font.name = '新細明體'
    run4.font.size = Pt(12)
    run4._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    doc.add_paragraph()
    
    # 第二個表格：學號和姓名（根據官方格式）
    # 創建2行（學號、姓名）+ 最多4名成員 = 6行
    table2 = doc.add_table(rows=6, cols=5)
    table2.style = 'Table Grid'
    
    # 第一行：學號標題
    header_cells = table2.rows[0].cells
    header_cells[0].text = ''
    for i in range(1, 5):
        para = header_cells[i].paragraphs[0]
        run = para.add_run('學號')
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
        run.bold = True
    
    # 第二行：姓名標題
    name_row = table2.rows[1].cells
    name_row[0].text = ''
    for i in range(1, 5):
        para = name_row[i].paragraphs[0]
        run = para.add_run('姓名')
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
        run.bold = True
    
    # 添加組長和組員行（從第3行開始）
    roles = ['組長', '組員', '組員', '組員']
    for idx, role in enumerate(roles):
        row_cells = table2.rows[idx + 2].cells  # 從第3行開始（索引2）
        para = row_cells[0].paragraphs[0]
        run = para.add_run(role)
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
        
        # 學號和姓名欄位留空供填寫
        for i in range(1, 5):
            para = row_cells[i].paragraphs[0]
            # 留空供使用者填寫
    
    doc.add_paragraph()
    doc.add_paragraph()
    
    # 摘要部分（根據官方格式）
    # 創建摘要表格
    abstract_table = doc.add_table(rows=1, cols=1)
    abstract_table.style = 'Table Grid'
    abstract_cell = abstract_table.rows[0].cells[0]
    
    # 摘要標題
    title_para = abstract_cell.paragraphs[0]
    title_run = title_para.add_run('摘要')
    title_run.font.name = '新細明體'
    title_run.font.size = Pt(12)
    title_run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    title_run.bold = True
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 摘要內容
    content_para = abstract_cell.add_paragraph()
    content_para.paragraph_format.line_spacing = 1.0
    content_run = content_para.add_run('\n【請在此填入摘要內容，建議200-300字，簡要說明專題的研究目的、方法、主要成果等】\n\n')
    content_run.font.name = '新細明體'
    content_run.font.size = Pt(12)
    content_run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    doc.add_page_break()
    
    # 內文標題
    content_titles = [
        '專題研究動機與目的',
        '現有相關研究概況及比較',
        '設計原理',
        '研究方法與步驟',
        '系統實現與實驗',
        '專題重要貢獻',
        '團隊合作方式',
        '效能評估與成果',
        '結論'
    ]
    
    for title in content_titles:
        heading = doc.add_heading(title, level=1)
        for run in heading.runs:
            run.font.name = '新細明體'
            run.font.size = Pt(12)
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
            run.bold = True
        
        # 添加內容段落
        content_para = doc.add_paragraph('【請在此填入' + title + '的內容】')
        content_para_format = content_para.paragraph_format
        content_para_format.line_spacing = 1.0
        for run in content_para.runs:
            run.font.name = '新細明體'
            run.font.size = Pt(12)
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
        
        doc.add_paragraph()
    
    doc.add_page_break()
    
    # 參考文獻
    ref_heading = doc.add_heading('參考文獻', level=1)
    for run in ref_heading.runs:
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
        run.bold = True
    
    # 參考文獻示例
    ref_para = doc.add_paragraph('【中文參考文獻請列於前】')
    ref_para_format = ref_para.paragraph_format
    ref_para_format.line_spacing = 1.0
    for run in ref_para.runs:
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    ref_para2 = doc.add_paragraph('【英文參考文獻請依序編號列於後】')
    ref_para2_format = ref_para2.paragraph_format
    ref_para2_format.line_spacing = 1.0
    for run in ref_para2.runs:
        run.font.name = '新細明體'
        run.font.size = Pt(12)
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    # 日期
    doc.add_paragraph()
    doc.add_paragraph()
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    date_run = date_para.add_run('中華民國     年     月')
    date_run.font.name = '新細明體'
    date_run.font.size = Pt(12)
    date_run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
    
    # 設置所有段落的字體格式
    def set_chinese_font(paragraph):
        """設置段落的中文字體"""
        for run in paragraph.runs:
            # 中文使用新細明體
            run.font.name = '新細明體'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '新細明體')
            run.font.size = Pt(12)
    
    # 設置英文和數字使用 Times New Roman
    # 注意：這需要在實際編輯時手動調整，因為 docx 無法完美區分中文、英文、數字
    
    return doc

if __name__ == '__main__':
    print("正在生成專題報告模板...")
    doc = create_report_template()
    output_file = '專題報告模板.docx'
    doc.save(output_file)
    print(f"模板已生成：{output_file}")
    print("\n注意事項：")
    print("1. 請在 Word 中打開生成的文件，檢查並調整格式")
    print("2. 英文和數字部分請手動設置為 Times New Roman 12pt")
    print("3. 標點符號請使用全型標點符號")
    print("4. 請添加頁碼（插入 > 頁碼 > 頁面底端 > 置中）")
    print("5. 圖表請按照要求編號（表1、表2、圖1、圖2等）")
