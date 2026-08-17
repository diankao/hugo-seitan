import os
import re
from pathlib import Path


def has_hugo_frontmatter(file_path):
    """
    检查文件是否有Hugo格式的frontmatter
    支持YAML格式（---）和TOML格式（+++）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查YAML格式：--- ... ---
        yaml_pattern = r'^---\s*\n.*?\n---\s*\n'
        yaml_match = re.match(yaml_pattern, content, re.DOTALL)
        
        # 检查TOML格式：+++ ... +++
        toml_pattern = r'^\+\+\+\s*\n.*?\n\+\+\+\s*\n'
        toml_match = re.match(toml_pattern, content, re.DOTALL)
        
        return yaml_match is not None or toml_match is not None
        
    except Exception as e:
        print(f"  [ERROR] 读取文件失败: {e}")
        return False


def find_markdown_files(root_dir):
    """
    递归查找所有Markdown文件
    """
    md_files = []
    for root, dirs, files in os.walk(root_dir):
        # 忽略包含"待解析"的目录
        dirs[:] = [d for d in dirs if '待解析' not in d]
        
        for file in files:
            if file.lower().endswith('.md'):
                md_files.append(os.path.join(root, file))
    return md_files


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"正在扫描目录: {root_dir}")
    print("=" * 80)
    
    md_files = find_markdown_files(root_dir)
    
    if not md_files:
        print("未找到任何Markdown文件")
        return
    
    print(f"共找到 {len(md_files)} 个Markdown文件")
    print()
    
    invalid_files = []
    
    for md_file in md_files:
        if not has_hugo_frontmatter(md_file):
            invalid_files.append(md_file)
    
    if invalid_files:
        print(f"发现 {len(invalid_files)} 个文件没有Hugo格式的frontmatter:")
        print("-" * 80)
        
        for i, file_path in enumerate(invalid_files, 1):
            # 计算相对路径，使输出更易读
            rel_path = os.path.relpath(file_path, root_dir)
            print(f"{i:3d}. {rel_path}")
        
        print("-" * 80)
        print(f"总计: {len(invalid_files)} 个不符合格式的文件")
    else:
        print("✓ 所有Markdown文件都包含Hugo格式的frontmatter")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
