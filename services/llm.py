"""LLM 封装：全项目唯一创建 ChatOpenAI 的地方。

为什么单独一层？
换模型、加日志、加缓存、统一超时/重试 —— 都只改这一个文件。
（企业里还会在这层接 LangSmith / Langfuse 做 tracing，M4 讲）
"""
from langchain_openai import ChatOpenAI

from config import settings


def get_llm() -> ChatOpenAI:
    """工厂函数：每次调用返回新的 LLM 实例。"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,   # DeepSeek 等 OpenAI 兼容厂商填这行；OpenAI 官方可不填
        temperature=settings.llm_temperature,
        timeout=60,
        max_retries=2,
    )
