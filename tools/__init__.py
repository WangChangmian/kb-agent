"""工具集：Agent（Function Calling）可调用的外部能力。

设计原则：
- 每个工具一个模块，职责单一
- 工具函数的 docstring 就是给模型看的"说明书"（能力 / 入参 / 适用场景 / 禁止场景）
- 工具必须返回结构化结果（dict 或 str），**不要 print**（打印会污染日志与输出流）
"""
from tools.employee import query_leave_balance
from tools.knowledge import search_knowledge_base

ALL_TOOLS = [query_leave_balance, search_knowledge_base]

__all__ = ["query_leave_balance", "search_knowledge_base", "ALL_TOOLS"]
