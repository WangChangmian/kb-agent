"""知识库检索工具：把 RAG 检索包装成 Agent 可调用的工具（"RAG 即工具"）。

这样 Agent 同时具备两种能力：
- 静态知识（制度、手册）→ search_knowledge_base（向量检索）
- 动态私有数据（员工年假余额）→ query_leave_balance（查库）
"""
from langchain_core.tools import tool

from services.retriever import retrieve


@tool
def search_knowledge_base(question: str) -> str:
    """在企业知识库（员工手册、公司制度）中检索相关内容。

    适用场景：问题涉及公司制度、流程、规定，例如年假规则、加班计算、报销流程、
    远程办公政策、培训补贴等。
    """
    docs = retrieve(question)
    if not docs:
        return "知识库中未找到相关内容。"
    return "\n\n".join(d.page_content for d in docs)
