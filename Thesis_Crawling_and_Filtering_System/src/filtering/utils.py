import glob
import os
from pathlib import Path

def get_filename_with_suffix(file_path, suffix):
    """在文件名后添加后缀，保留扩展名。"""
    p = Path(file_path)
    return f"{p.stem}_{suffix}{p.suffix}"

def get_json_files():
    """获取用于粗筛的JSON文件列表。"""
    all_files = glob.glob("*.json") + glob.glob("arxiv_papers/*.json") + glob.glob("conference_papers/*.json")
    excluded = {'config.json', 'last_crawl_time.json', 'failed_intervals.json'}
    # 过滤掉配置文件、中间结果和最终结果文件
    return sorted([
        f for f in all_files 
        if os.path.basename(f) not in excluded 
        and '_coarse_' not in f 
        and '_fine_' not in f
    ])

def get_result_files():
    """获取粗筛结果文件列表，用于精排输入。"""
    return sorted([f for f in glob.glob("results/coarse_screening/*.json") if 'coarse_final' in f])

def get_file_path(dropdown_value, upload_file):
    """获取文件路径，优先使用上传的文件。"""
    if upload_file is not None:
        # Gradio 的 File 组件返回一个带有 .name 属性的临时文件对象
        return upload_file.name
    elif dropdown_value:
        return dropdown_value
    else:
        return None
