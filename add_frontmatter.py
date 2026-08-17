import os
import re
from datetime import datetime

base_dir = r"d:\source\blog\content\posts\seitan"

def extract_title_and_tags(content):
    title = "未命名文档"
    tags = []
    
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    
    tags_match = re.search(r'## 标签\s*\n(.+?)(?=##|$)', content, re.DOTALL)
    if tags_match:
        tag_text = tags_match.group(1)
        tags = [tag.strip() for tag in tag_text.split() if tag.startswith('#')]
    
    return title, tags

def add_frontmatter(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if content.startswith('+++'):
        return False
    
    title, tags = get_file_info(file_path)
    date = get_file_date(file_path)
    
    frontmatter = f'''+++
title = '{title}'
date = {date}
draft = false
categories = ['技术文档']
tags = {tags}
+++

'''
    
    new_content = frontmatter + content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return True

def get_file_info(file_path):
    filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(filename)[0]
    
    title = name_without_ext.replace('_', ' ')
    if title.startswith('000'):
        title = title[5:]
    
    tags = []
    dir_name = os.path.basename(os.path.dirname(file_path))
    
    if '嵌入式' in dir_name or 'DMA' in filename or '驱动' in dir_name:
        tags = ['嵌入式']
    elif '操作系统' in dir_name or 'FreeRTOS' in filename:
        tags = ['操作系统', 'FreeRTOS']
    elif '通信协议' in dir_name:
        tags = ['通信协议']
    elif 'C语言' in dir_name or 'C++' in filename:
        tags = ['C++']
    elif '算法' in dir_name:
        tags = ['算法']
    elif '综合问题' in dir_name:
        tags = ['面试']
    elif '项目经验' in dir_name:
        tags = ['项目']
    
    return title, str(tags)

def get_file_date(file_path):
    filename = os.path.basename(file_path)
    date_match = re.search(r'(\d{8})', filename)
    
    if date_match:
        date_str = date_match.group(1)
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        return f'{year}-{month}-{day}T00:00:00+08:00'
    
    return '2026-02-27T00:00:00+08:00'

def process_directory(directory):
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.md') and file != 'REPOSITORY_SPEC.md' and file != 'TASK.md':
                file_path = os.path.join(root, file)
                try:
                    if add_frontmatter(file_path):
                        print(f"已处理: {file_path}")
                        count += 1
                    else:
                        print(f"跳过 (已有 front matter): {file_path}")
                except Exception as e:
                    print(f"错误 {file_path}: {e}")
    
    return count

if __name__ == '__main__':
    count = process_directory(base_dir)
    print(f"\n处理完成! 共处理 {count} 个文件")
