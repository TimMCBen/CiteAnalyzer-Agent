# -*- coding: utf-8 -*-
"""
该模块负责将用户定义的简洁查询语法转换为 arXiv API 可接受的官方查询语法，
并从中提取用于后续处理的关键词。
"""

import re
from typing import List, Tuple, Dict, Any

def parse_advanced_query(query: str) -> Tuple[str, List[str]]:
    """
    解析高级查询字符串，返回转换后的 arXiv API 查询和关键词列表。
    这个统一的函数确保了查询逻辑和关键词提取逻辑的一致性。

    Args:
        query (str): 用户输入的高级查询字符串。

    Returns:
        Tuple[str, List[str]]:
            - 转换后的 arXiv API 查询字符串。
            - 从查询中提取的关键词列表（不包括 NOT 之后的词）。
    """
    if not query:
        return "", []

    # 1. 提取所有独立的词、带引号的短语、操作符和括号
    # 这个正则表达式能更好地处理各种组合
    tokens = re.findall(r'"[^"]+"|\b[\w-]+\b|\(|\)|\b(?:AND|OR|NOT)\b', query, re.IGNORECASE)

    translated_tokens = []
    keywords = set()
    is_negated = False  # 标记下一个词是否在 NOT 之后

    for token in tokens:
        token_upper = token.upper()

        if token_upper in ["AND", "OR", "(", ")"]:
            translated_tokens.append(token)
            is_negated = False
        elif token_upper == "NOT":
            # arXiv API 使用 ANDNOT
            translated_tokens.append("ANDNOT")
            is_negated = True
        else:
            # 这是一个关键词或短语
            clean_token = token.strip('"')
            
            # 根据是否在 NOT 之后，决定是否加入关键词列表
            if not is_negated:
                keywords.add(clean_token)
            
            # 检查是否有字段前缀 (例如 title:word)
            # 注意：为了简化，我们在这里假设高级模式用户会自己写 ti: 或 abs:
            # 但为了稳健性，我们默认搜索两者
            if ":" in token:
                 # 支持用户自己写 ti:"some phrase" 或 abs:word
                field, term = token.split(":", 1)
                term = term.strip('"')
                if field.lower() in ["ti", "title"]:
                    translated_tokens.append(f'ti:"{term}"')
                elif field.lower() in ["abs", "abstract"]:
                    translated_tokens.append(f'abs:"{term}"')
                else: # 如果前缀不认识，就默认搜索
                    translated_tokens.append(f'(ti:"{clean_token}" OR abs:"{clean_token}")')
            else:
                # 默认在标题和摘要中搜索
                translated_tokens.append(f'(ti:"{clean_token}" OR abs:"{clean_token}")')
            
            is_negated = False

    final_query = " ".join(translated_tokens)
    # 清理多余的空格和确保操作符两边有空格
    final_query = re.sub(r'\s+(AND|OR|ANDNOT)\s+', r' \1 ', final_query, flags=re.IGNORECASE)
    final_query = re.sub(r'\(\s+', '(', final_query)
    final_query = re.sub(r'\s+\)', ')', final_query)

    return final_query.strip(), sorted(list(keywords))

def extract_keywords_from_config(crawler_config: Dict[str, Any]) -> List[str]:
    """
    从爬虫配置中提取所有用于搜索的关键词。
    """
    query_mode = crawler_config.get("query_mode", "simple")
    
    if query_mode == "advanced":
        query = crawler_config.get("advanced_query", "")
        _, keywords = parse_advanced_query(query)
        return keywords
    else:  # simple mode
        keywords_config = crawler_config.get("keywords", {})
        must_kws = keywords_config.get("must", [])
        optional_kws = keywords_config.get("optional", [])
        return sorted(list(set(must_kws + optional_kws)))

# --- 旧函数占位，以防其他地方有导入但未使用 ---
def translate_simplified_query(query: str) -> str:
    """
    旧函数的包装器，现在使用新的解析器。
    """
    final_query, _ = parse_advanced_query(query)
    return final_query
