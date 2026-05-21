import asyncio
import json
import os
from openai import AsyncOpenAI
import time

# 默认配置 (与你的 Gradio 应用保持一致)
DEFAULT_CONFIG = {
    "api_key": "38665e80-9c05-44fb-9b12-cacc43e800f0", # 请在这里替换为你的实际API Key，或者在config.json中配置
    "base_url": "https://ark.cn-beijing.volces.com/api/v3", # 使用你之前成功配置的Gemini代理URL
    "model": "doubao-seed-1-6-flash-250828", # 使用你之前成功的Gemini模型
    "rounds": 3,
    "max_concurrent": 5
}

# 预设提示词 (与你的 Gradio 应用保持一致)
COARSE_SYSTEM_PROMPT = """
Determine if this paper title is related to emotional support, psychological counseling, or multi-turn dialogue. Return True if there is any relevant content, otherwise return False.
<True/False>
"""

FINE_SYSTEM_PROMPT = """
Please carefully read the title and abstract of the paper and determine whether the paper is closely related to any of the following topics:
- Emotional support
- Psychological counseling
- Multi-turn dialogue
- Dialogue systems

Please conduct an in-depth analysis based on the content of the abstract. Return "True" only if the core content of the paper is indeed related to the above topics.
If the paper only mentions relevant concepts slightly or mainly focuses on other fields, return "False".

<True/False>
"""

def load_config():
    """加载配置文件，如果不存在则创建默认配置文件"""
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 确保加载的配置包含默认值中所有键，防止KeyError
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = default_value
            return config
    else:
        # 创建默认配置文件
        print(f"配置文件 '{config_path}' 不存在，创建默认配置...")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG

async def check_paper_relevance_with_retry(client, paper_data, system_prompt, max_retries=3):
    """
    模拟粗筛逻辑：基于标题检查论文相关性，带重试机制。
    与 Gradio 应用中的同名函数功能一致。
    """
    for attempt in range(max_retries):
        try:
            title_text = paper_data.get('title', '').strip()
            # 兼容性处理，如果标题包含'author'，取前面部分
            clean_title = title_text.split('author')[0].strip()
            user_content = f"论文标题: {clean_title}"

            print(f"  [Coarse Screening] Attempt {attempt + 1}: Checking title '{clean_title[:70]}...'")

            response = await client.chat.completions.create(
                model=client.model, # client.model 是在创建 client 实例后赋值的
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0, # 粗筛通常需要确定性结果
                max_tokens=5, # 预期输出是 True/False
            )
            
            # 兼容处理content为空的情况
            result_content = response.choices[0].message.content.strip()
            if not result_content and hasattr(response.choices[0].message, 'reasoning_content'):
                result_content = response.choices[0].message.reasoning_content.strip()

            is_relevant = "True" in result_content
            print(f"  [Coarse Screening] Result for '{clean_title[:70]}...': {is_relevant} (Raw: '{result_content}')")
            return paper_data, is_relevant
        except Exception as e:
            print(f"  [Coarse Screening] API调用失败 (尝试 {attempt + 1}/{max_retries}) for '{clean_title[:70]}...': {e}")
            if attempt < max_retries - 1:
                print("  等待60秒后重试...")
                await asyncio.sleep(60)
            else:
                print(f"  处理标题 '{clean_title[:70]}...' 时出错 (已重试{max_retries}次), 标记为不相关。")
                return paper_data, False

async def check_paper_relevance_detailed_with_retry(client, paper_data, system_prompt, max_retries=3):
    """
    模拟精排逻辑：基于标题和摘要检查论文相关性，带重试机制。
    与 Gradio 应用中的同名函数功能一致。
    """
    for attempt in range(max_retries):
        try:
            title_text = paper_data.get('title', '').strip()
            abstract_text = paper_data.get('abstract', '').strip()
            clean_title = title_text.split('author')[0].strip()
            user_content = f"论文标题: {clean_title}\n\n论文摘要: {abstract_text}"

            print(f"  [Fine Screening] Attempt {attempt + 1}: Checking full paper '{clean_title[:70]}...'")

            response = await client.chat.completions.create(
                model=client.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0, # 精排也倾向于确定性结果
                max_tokens=5, # 预期输出是 True/False
            )

            # 兼容处理content为空的情况
            result_content = response.choices[0].message.content.strip()
            if not result_content and hasattr(response.choices[0].message, 'reasoning_content'):
                result_content = response.choices[0].message.reasoning_content.strip()
                
            is_relevant = "True" in result_content
            print(f"  [Fine Screening] Result for '{clean_title[:70]}...': {is_relevant} (Raw: '{result_content}')")
            return paper_data, is_relevant
        except Exception as e:
            print(f"  [Fine Screening] API调用失败 (尝试 {attempt + 1}/{max_retries}) for '{clean_title[:70]}...': {e}")
            if attempt < max_retries - 1:
                print("  等待60秒后重试...")
                await asyncio.sleep(60)
            else:
                print(f"  处理论文 '{clean_title[:70]}...' 时出错 (已重试{max_retries}次), 标记为不相关。")
                return paper_data, False

async def main():
    config = load_config()
    
    # 确保 config.json 中有正确的 API Key 和 Base URL
    if config["api_key"] == "YOUR_API_KEY_HERE" or not config["api_key"]:
        print("警告: API Key 未设置。请在 config.json 中更新 'api_key'。")
        # return # 实际运行中应该退出
    
    print(f"使用配置: Base URL={config['base_url']}, Model={config['model']}")

    client = AsyncOpenAI(
        api_key=config["api_key"], 
        base_url=config["base_url"],
        timeout=60.0
    )
    client.model = config["model"] # 将模型名称附加到客户端实例，方便传递

    # --- 模拟论文数据 ---
    mock_papers = [
        {
            "title": "A Deep Learning Approach for Emotional Support Chatbots author(John Doe)",
            "abstract": "This paper proposes a novel deep learning model for developing emotional support chatbots that can understand user emotions and provide empathetic responses. We evaluate our model on a dataset of online counseling conversations."
        },
        {
            "title": "Optimizing Multi-turn Dialogue Systems with Reinforcement Learning",
            "abstract": "We present a new framework for multi-turn dialogue management using deep reinforcement learning. Our system achieves state-of-the-art performance on task-oriented dialogue benchmarks."
        },
        {
            "title": "Blockchain for Secure Data Storage in IoT Devices",
            "abstract": "This research explores the application of blockchain technology to enhance data security and privacy in Internet of Things (IoT) ecosystems. We propose a decentralized storage solution."
        },
        {
            "title": "Investigating User Behavior in Virtual Reality Gaming Environments",
            "abstract": "This study analyzes user interaction patterns and immersion levels in various virtual reality gaming scenarios, identifying key factors influencing player engagement and retention."
        },
        {
            "title": "Conversational AI for Mental Health Support",
            "abstract": "We explore the use of conversational AI agents to deliver accessible and scalable mental health support, focusing on cognitive behavioral therapy techniques within a dialogue system context."
        }
    ]

    print("\n--- 开始粗筛 (基于标题) ---")
    coarse_results = await asyncio.gather(*[
        check_paper_relevance_with_retry(client, paper, COARSE_SYSTEM_PROMPT) 
        for paper in mock_papers
    ])
    
    relevant_for_fine_screening = [paper for paper, is_relevant in coarse_results if is_relevant]
    print(f"\n粗筛结果：找到 {len(relevant_for_fine_screening)} 篇相关论文准备精排。")

    # if relevant_for_fine_screening:
    #     print("\n--- 开始精排 (基于标题和摘要) ---")
    #     fine_results = await asyncio.gather(*[
    #         check_paper_relevance_detailed_with_retry(client, paper, FINE_SYSTEM_PROMPT)
    #         for paper in relevant_for_fine_screening
    #     ])
        
    #     final_relevant_papers = [paper for paper, is_relevant in fine_results if is_relevant]
    #     print(f"\n精排结果：最终找到 {len(final_relevant_papers)} 篇论文。")
    #     print("\n最终相关论文列表:")
    #     for paper in final_relevant_papers:
    #         print(f"- {paper['title']}")
    # else:
    #     print("粗筛未找到相关论文，跳过精排。")

if __name__ == "__main__":
    # 配置 httpx 和 httpcore 的日志以查看详细请求信息
    import logging
    logging.basicConfig(level=logging.INFO) # 默认INFO，只显示重要信息
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    logging.getLogger("openai").setLevel(logging.DEBUG) # 确保openai库的日志也输出
    
    # 手动设置 HTTP 客户端调试级别
    import http.client as http_client
    http_client.HTTPConnection.debuglevel = 1
    http_client.HTTPSConnection.debuglevel = 1

    asyncio.run(main())
