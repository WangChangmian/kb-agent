"""检索服务（M1 课一起实现）。

链路（在线阶段，每次提问都走）：
    问题向量化 -> 向量库相似度检索 top_k -> （M2 加 rerank 重排）
    -> 拼进 Prompt -> LLM 生成

TODO（下次课填）：
1. 问题转 embedding，similarity_search 取 top_k 块
2. 过滤低于 score_threshold 的（防止拿无关内容硬答）
3. 把检索结果拼成「引用来源」，返回给上层（M2 展示出处）
"""
from services.vector_store import get_vector_store
from config import settings
from langchain_core.prompts import ChatPromptTemplate
from services.llm import get_llm

def retrieve(question: str, k: int | None = None) -> list:
    vs = get_vector_store()
    docs_with_scores = vs.similarity_search_with_relevance_scores(
        question, k=k or settings.retriever_top_k)  # ① k 不再写死，用配置

    filtered = []
    for doc, score in docs_with_scores:
        if score >= settings.retriever_score_threshold:
            doc.metadata["score"] = round(score, 3)  # ② 分数写进 metadata（M2 展示来源要用）
            filtered.append(doc)

    return filtered

def _build_chain():
    """拼 Prompt + LLM 的链，ask 和 ask_stream 共用（DRY：别重复自己）。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是企业知识库助手。只依据【参考资料】回答，资料里没有的内容，明确说“资料中未找到”，不要编造。"),
        ("human", "【参考资料】\n{context}\n\n【问题】\n{question}"),
    ])
    return prompt | get_llm()

def ask(question: str):
    docs = retrieve(question)
    context =  "\n\n".join(d.page_content for d in docs)
    chain = _build_chain()
    answer = chain.invoke({"context": context, "question": question}).content
    return answer

def ask_stream(question: str):
    docs = retrieve(question)
    context =  "\n\n".join(d.page_content for d in docs)
    chain = _build_chain()
    for chunk in chain.stream({"context": context, "question": question}):
        if chunk.content:  # ← 新增：跳过空块
            print(chunk.content, end="", flush=True)
    print()

if __name__ == "__main__":
    import time

    question = "请详细介绍一下公司的年假制度、加班政策、报销流程和远程办公政策"

    # 演示1：看分块明细（模型怎么吐的）
    docs = retrieve(question)
    context = "\n\n".join(d.page_content for d in docs)
    chain = _build_chain()
    print("=== 分块明细 ===")
    for i, chunk in enumerate(chain.stream({"context": context, "question": question})):
        if chunk.content:  # ← 新增：跳过空块
            print(f"块{i}: {chunk.content!r}")

    # 演示2：放慢的打字机效果
    print("\n=== 打字机效果（0.05秒/块）===")
    for chunk in chain.stream({"context": context, "question": question}):
        print(chunk.content, end="", flush=True)
        time.sleep(0.05)
    print()