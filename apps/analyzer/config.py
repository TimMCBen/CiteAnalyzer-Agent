from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def build_llm() -> ChatOpenAI:
    load_dotenv()

    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")
    model = os.getenv("MODEL", "gpt-5-4")

    if not api_key:
        raise ValueError("API_KEY is required in .env")

    return ChatOpenAI(api_key=api_key, base_url=base_url, model=model, temperature=0)
