"""
解析 .odt 文件内容
"""

import zipfile
import xml.etree.ElementTree as ET
import sys

def parse_odt(filename):
    """解析 ODT 文件並提取文本内容"""
    
    # ODT 是一個 ZIP 文件，content.xml 包含主要內容
    with zipfile.ZipFile(filename) as odt_file:
        # 讀取 content.xml
        content_xml = odt_file.read('content.xml')
        
        # 解析 XML
        root = ET.fromstring(content_xml)
        
        # 定義命名空間
        namespaces = {
            'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
            'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
            'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0'
        }
        
        # 提取所有文本
        text_elements = []
        
        # 獲取 body
        body = root.find('.//office:body', namespaces)
        if body is not None:
            text_body = body.find('.//office:text', namespaces)
            if text_body is not None:
                text_elements = extract_text_recursive(text_body, namespaces)
        
        return text_elements

def extract_text_recursive(element, namespaces):
    """遞歸提取文本內容"""
    result = []
    
    # 處理段落
    if element.tag.endswith('}p'):
        para_text = get_element_text(element)
        if para_text.strip():
            result.append(('paragraph', para_text))
    
    # 處理標題
    elif element.tag.endswith('}h'):
        heading_text = get_element_text(element)
        level = element.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}outline-level', '1')
        if heading_text.strip():
            result.append(('heading', heading_text, level))
    
    # 處理列表項
    elif element.tag.endswith('}list-item'):
        for child in element:
            result.extend(extract_text_recursive(child, namespaces))
    
    # 處理表格
    elif element.tag.endswith('}table'):
        result.append(('table_start', ''))
        for row in element.findall('.//{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row', namespaces):
            row_data = []
            for cell in row.findall('.//{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell', namespaces):
                cell_text = get_element_text(cell)
                row_data.append(cell_text)
            if row_data:
                result.append(('table_row', row_data))
        result.append(('table_end', ''))
    
    # 遞歸處理子元素
    else:
        for child in element:
            result.extend(extract_text_recursive(child, namespaces))
    
    return result

def get_element_text(element):
    """獲取元素及其子元素的所有文本"""
    text = element.text or ''
    for child in element:
        text += get_element_text(child)
        if child.tail:
            text += child.tail
    return text

def format_output(text_elements):
    """格式化輸出"""
    output = []
    for item in text_elements:
        if item[0] == 'heading':
            output.append(f"\n{'#' * int(item[2])} {item[1]}\n")
        elif item[0] == 'paragraph':
            output.append(item[1])
        elif item[0] == 'table_start':
            output.append("\n[TABLE]")
        elif item[0] == 'table_row':
            output.append(" | ".join(item[1]))
        elif item[0] == 'table_end':
            output.append("[/TABLE]\n")
    return '\n'.join(output)

if __name__ == '__main__':
    filename = '@清華大學資工系專題報告格式_經20170511課程委員會通過.odt'
    
    try:
        text_elements = parse_odt(filename)
        output = format_output(text_elements)
        
        # 輸出到文件
        with open('官方格式文檔內容.txt', 'w', encoding='utf-8') as f:
            f.write(output)
        
        print("已成功提取文檔內容到: 官方格式文檔內容.txt")
        print("\n" + "="*50)
        print(output)
        
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()







