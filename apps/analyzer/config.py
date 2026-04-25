from __future__ import annotations

import os
from typing import Any


def build_llm() -> Any:
    try:
        from dotenv import load_dotenv
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("LLM dependencies are not installed") from exc

    load_dotenv()

    api_key = (os.getenv("API_KEY") or "").strip()
    base_url = (os.getenv("BASE_URL") or "").strip()
    model = (os.getenv("MODEL") or "").strip()

    if not api_key:
        raise ValueError("API_KEY is required in .env")
    if not base_url:
        raise ValueError("BASE_URL is required in .env")
    if not model:
        raise ValueError("MODEL is required in .env")

    return ChatOpenAI(api_key=api_key, base_url=base_url, model=model, temperature=0)
