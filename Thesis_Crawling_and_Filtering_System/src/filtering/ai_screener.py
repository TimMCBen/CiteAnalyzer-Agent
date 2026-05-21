import asyncio
import json
import os
import aiofiles
import gradio as gr
from openai import AsyncOpenAI

from src.config_manager import config_manager
from .utils import get_filename_with_suffix, get_file_path

async def check_paper_relevance_with_retry(client, paper_data, system_prompt, max_retries=3):
    """检查单个论文的相关性（粗筛）- 带重试机制"""
    for attempt in range(max_retries):
        try:
            title_text = paper_data.get('title', '').strip()
            clean_title = title_text.split('author')[0].strip()
            user_content = f"论文标题: {clean_title}"

            response = await client.chat.completions.create(
                model=client.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
            )
            result = response.choices[0].message.content.strip()
            return paper_data, "True" in result
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                print("等待60秒后重试...")
                await asyncio.sleep(60)
            else:
                print(f"处理标题 '{paper_data.get('title', 'N/A')}' 时出错 (已重试{max_retries}次): {e}")
                return paper_data, False

async def check_paper_relevance_detailed_with_retry(client, paper_data, system_prompt, max_retries=3):
    """基于标题和摘要检查单个论文的相关性（精排）- 带重试机制"""
    for attempt in range(max_retries):
        try:
            title_text = paper_data.get('title', '').strip()
            abstract_text = paper_data.get('abstract', '').strip()
            clean_title = title_text.split('author')[0].strip()
            content = f"论文标题: {clean_title}\n\n论文摘要: {abstract_text}"
            
            response = await client.chat.completions.create(
                model=client.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ]
            )
            result = response.choices[0].message.content.strip()
            return paper_data, "True" in result
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                print("等待60秒后重试...")
                await asyncio.sleep(60)
            else:
                print(f"处理论文 '{paper_data.get('title', 'N/A')}' 时出错 (已重试{max_retries}次): {e}")
                return paper_data, False

async def process_papers_single_round(client, papers_data, system_prompt, round_num, max_concurrent, is_fine=False, progress_callback=None):
    """单轮处理所有论文"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def limited_check(paper_data):
        async with semaphore:
            if is_fine:
                return await check_paper_relevance_detailed_with_retry(client, paper_data, system_prompt)
            else:
                print("ggg")
                return await check_paper_relevance_with_retry(client, paper_data, system_prompt)
    
    mode = "精排" if is_fine else "粗筛"
    print(f"开始第 {round_num} 轮{mode}检查 {len(papers_data)} 篇论文的相关性...")
    
    tasks = [limited_check(paper) for paper in papers_data if paper.get('title')]
    
    results = []
    completed = 0
    
    for completed_task in asyncio.as_completed(tasks):
        result = await completed_task
        results.append(result)
        completed += 1
        
        if progress_callback and len(tasks) > 0:
            progress = completed / len(tasks)
            progress_callback(progress, f"第{round_num}轮{mode}: {completed}/{len(tasks)}")
    
    relevant_papers = [paper_data for paper_data, is_relevant in results if is_relevant]
    
    print(f"第 {round_num} 轮{mode}找到 {len(relevant_papers)} 篇相关论文")
    
    return relevant_papers

async def coarse_screening(main_json_file, findings_json_file, system_prompt, config, progress_callback=None):
    """粗筛处理"""
    papers_data = []
    
    if not os.path.exists(main_json_file):
        return f"错误：文件 {main_json_file} 不存在"
    
    try:
        async with aiofiles.open(main_json_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            main_data = json.loads(content)
            if 'papers' in main_data:
                papers_data.extend(main_data['papers'])
                print(f"读取主会议论文: {len(main_data['papers'])} 篇")
    except Exception as e:
        return f"读取或解析主文件 {main_json_file} 失败: {e}"

    if findings_json_file and os.path.exists(findings_json_file):
        try:
            async with aiofiles.open(findings_json_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                findings_data = json.loads(content)
                if 'papers' in findings_data:
                    papers_data.extend(findings_data['papers'])
                    print(f"读取Findings论文: {len(findings_data['papers'])} 篇")
        except Exception as e:
            return f"读取或解析Findings文件 {findings_json_file} 失败: {e}"

    
    print(f"总共需要处理: {len(papers_data)} 篇论文")
    
    client = AsyncOpenAI(
        api_key=config["api_key"], 
        base_url=config["base_url"],
        timeout=60.0
    )
    client.model = config["model"]
    
    all_rounds_results = []
    rounds = config.get("rounds", 3)
    max_concurrent = config.get("max_concurrent", 50)
    
    for round_num in range(1, rounds + 1):
        if progress_callback:
            progress_callback(0, f"开始第{round_num}轮粗筛...")
        
        relevant_papers = await process_papers_single_round(
            client, papers_data, system_prompt, round_num, max_concurrent, False, progress_callback
        )
        all_rounds_results.append(relevant_papers)
        
        round_data = {
            "round": round_num,
            "total_papers": len(papers_data),
            "relevant_papers_count": len(relevant_papers),
            "relevant_papers": relevant_papers
        }
        
        output_filename = get_filename_with_suffix(main_json_file, f'coarse_round_{round_num}')
        output_file = os.path.join('results/coarse_screening', os.path.basename(output_filename))
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(round_data, ensure_ascii=False, indent=2))
        
        print(f"第 {round_num} 轮结果已保存到 {output_file}")
    
    all_relevant_papers = {}
    for round_papers in all_rounds_results:
        for paper in round_papers:
            if paper.get('title'):
                all_relevant_papers[paper['title']] = paper
    
    final_relevant_papers = list(all_relevant_papers.values())
    
    final_data = {
        "total_papers": len(papers_data),
        "rounds_count": rounds,
        "max_concurrent": max_concurrent,
        "round_results": [
            {
                "round": i,
                "count": len(round_papers)
            }
            for i, round_papers in enumerate(all_rounds_results, 1)
        ],
        "final_relevant_papers_count": len(final_relevant_papers),
        "relevant_papers": sorted(final_relevant_papers, key=lambda x: x.get('title', ''))
    }
    
    output_filename = get_filename_with_suffix(main_json_file, 'coarse_final')
    output_file = os.path.join('results/coarse_screening', os.path.basename(output_filename))
    async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(final_data, ensure_ascii=False, indent=2))
    
    round_stats = "\n".join([f"- 第{i}轮筛选：{len(round_papers)} 篇" for i, round_papers in enumerate(all_rounds_results, 1)])
    
    result_text = f"""
粗筛完成！

处理统计：
- 总论文数：{len(papers_data)}
- 处理轮数：{rounds} 轮
- 最大并发数：{max_concurrent}
{round_stats}
- 最终结果：{len(final_relevant_papers)} 篇

结果已保存到：{output_file}
"""
    
    return result_text

async def fine_screening(input_json_file, system_prompt, config, progress_callback=None):
    """精排处理"""
    if not os.path.exists(input_json_file):
        return f"错误：文件 {input_json_file} 不存在"
    
    try:
        async with aiofiles.open(input_json_file, 'r', encoding='utf-8') as f:
            content = await f.read()
            coarse_data = json.loads(content)
            papers_data = coarse_data.get('relevant_papers', [])
            print(f"读取粗排结果: {len(papers_data)} 篇论文")
    except Exception as e:
        return f"读取或解析文件 {input_json_file} 失败: {e}"

    client = AsyncOpenAI(
        api_key=config["api_key"], 
        base_url=config["base_url"],
        timeout=60.0
    )
    client.model = config["model"]
    
    all_rounds_results = []
    rounds = config.get("rounds", 3)
    max_concurrent = min(config.get("max_concurrent", 50), 30)
    
    for round_num in range(1, rounds + 1):
        if progress_callback:
            progress_callback(0, f"开始第{round_num}轮精排...")
        
        relevant_papers = await process_papers_single_round(
            client, papers_data, system_prompt, round_num, max_concurrent, True, progress_callback
        )
        all_rounds_results.append(relevant_papers)
        
        round_data = {
            "round": round_num,
            "type": "fine_ranking",
            "input_papers": len(papers_data),
            "relevant_papers_count": len(relevant_papers),
            "relevant_papers": relevant_papers
        }
        
        output_file = get_filename_with_suffix(input_json_file, f'fine_round_{round_num}')
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(round_data, ensure_ascii=False, indent=2))
        
        print(f"第 {round_num} 轮精排结果已保存到 {output_file}")
    
    all_relevant_papers = {}
    for round_papers in all_rounds_results:
        for paper in round_papers:
            if paper.get('title'):
                all_relevant_papers[paper['title']] = paper
    
    final_relevant_papers = list(all_relevant_papers.values())
    
    final_data = {
        "type": "fine_ranking_final",
        "input_papers": len(papers_data),
        "rounds_count": rounds,
        "max_concurrent": max_concurrent,
        "round_results": [
            {
                "round": i,
                "count": len(round_papers)
            }
            for i, round_papers in enumerate(all_rounds_results, 1)
        ],
        "final_relevant_papers_count": len(final_relevant_papers),
        "selection_rate": f"{len(final_relevant_papers)/len(papers_data)*100:.1f}%" if len(papers_data) > 0 else "0.0%",
        "relevant_papers": sorted(final_relevant_papers, key=lambda x: x.get('title', ''))
    }
    
    output_file = get_filename_with_suffix(input_json_file, 'fine_final')
    async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(final_data, ensure_ascii=False, indent=2))
    
    round_stats = "\n".join([f"- 第{i}轮精排：{len(round_papers)} 篇" for i, round_papers in enumerate(all_rounds_results, 1)])
    
    result_text = f"""
精排完成！

处理统计：
- 输入论文数：{len(papers_data)}
- 处理轮数：{rounds} 轮
- 最大并发数：{max_concurrent}
{round_stats}
- 最终结果：{len(final_relevant_papers)} 篇
- 精排率：{final_data['selection_rate']}

结果已保存到：{output_file}
"""
    
    return result_text

def run_coarse_screening_with_progress(main_dropdown, findings_dropdown, main_upload, findings_upload, system_prompt, progress=gr.Progress()):
    def progress_callback(prog, desc):
        progress(prog, desc=desc)
    
    main_file = get_file_path(main_dropdown, main_upload)
    findings_file = get_file_path(findings_dropdown, findings_upload)
    
    if not main_file:
        return "错误：请选择主会议论文文件"
    
    config = config_manager.get_config("filtering").get("ai_screener", {})
    return asyncio.run(coarse_screening(main_file, findings_file, system_prompt, config, progress_callback))

def run_fine_screening_with_progress(input_dropdown, input_upload, system_prompt, progress=gr.Progress()):
    def progress_callback(prog, desc):
        progress(prog, desc=desc)
    
    input_file = get_file_path(input_dropdown, input_upload)
    
    if not input_file:
        return "错误：请选择输入文件"
    
    config = config_manager.get_config("filtering").get("ai_screener", {})
    return asyncio.run(fine_screening(input_file, system_prompt, config, progress_callback))
