"""检索服务。

链路（在线阶段，每次提问都走）：
    问题向量化 -> 向量库召回 -> embedding 阈值粗筛 -> rerank 精排
    -> rerank 阈值判定「库里有没有答案」-> 拼进 Prompt -> LLM 生成

为什么要两阶段（实测数据支撑）：
- embedding 相似度对中文区分度很差：同一个问题，含答案的块 0.757、无关块 0.579，
  差距只有 0.18，**没法设绝对阈值**；
- 换成 cross-encoder 精排后：含答案的块 0.94、无关块 0.001，差距 0.94，**阈值随便设**。
- 更有价值的是：无关问题的 rerank 分数接近 0（实测 0.005 / 0.0006 / 0.0005），
  于是可以可靠地判断"知识库里根本没有答案"，直接拒答，不给模型编造的机会。

三道关卡各司其职（召回负责别漏，精排负责别错）：
    recall_k=16 召回 -> embedding 0.2 粗筛 -> rerank 取 top_k -> rerank 0.1 判定有无答案
"""
import json
import urllib.request

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from services.llm import get_llm
from services.vector_store import get_vector_store


def _rerank(question: str, docs: list[Document], top_n: int) -> list[Document]:
    """用 cross-encoder 对候选文档精排，返回 top_n 条（分数写进 metadata["rerank_score"]）。

    与向量相似度的区别：
    - embedding：把"问题"和"文档"各自编码成向量，比方向 -> 只能判断"像不像"
    - rerank   ：把两者拼在一起送进模型       -> 能判断"这段文字能不能回答这个问题"

    rerank 属于"锦上添花"：失败时降级为原顺序，绝不拖垮整条问答链路。
    """
    if not docs:
        return []

    api_key = (
        settings.rerank_api_key
        or settings.embedding_api_key
        or settings.llm_api_key
    )
    payload = {
        "model": settings.rerank_model,
        "query": question,
        "documents": [d.page_content for d in docs],
        "top_n": top_n,
        "return_documents": False,
    }
    req = urllib.request.Request(
        settings.rerank_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return docs[:top_n]              # 降级：精排失败就用向量顺序

    picked: list[tuple[float, Document]] = []
    for item in data.get("results", []):
        doc = docs[item["index"]]        # API 返回的是原数组下标
        doc.metadata["rerank_score"] = round(item["relevance_score"], 4)
        picked.append((item["relevance_score"], doc))

    picked.sort(key=lambda x: -x[0])
    return [doc for _, doc in picked]


def retrieve(question: str, k: int | None = None) -> list[Document]:
    """三道关卡：召回（别漏）-> embedding 粗筛 -> rerank 精排 + 阈值（别错）。"""
    vs = get_vector_store()

    # ① 召回：多取一些，因为后面要靠 rerank 精挑
    docs_with_scores = vs.similarity_search_with_relevance_scores(
        query=question, k=settings.retriever_recall_k
    )

    # ② 粗筛：embedding 分数太低直接丢（用便宜的手段先挡掉明显不沾边的）
    filtered: list[Document] = []
    for doc, score in docs_with_scores:
        if score >= settings.retriever_score_threshold:
            doc.metadata["score"] = round(score, 3)
            filtered.append(doc)

    # ③ 精排 + 硬防线：rerank 分数达不到门槛 = 这段资料回答不了这个问题
    reranked = _rerank(question, filtered, top_n=k or settings.retriever_top_k)
    return [
        d for d in reranked
        if d.metadata.get("rerank_score", 0) >= settings.rerank_score_threshold
    ]


def _build_chain():
    """拼 Prompt + LLM 的链，ask 和 ask_stream 共用（DRY：别重复自己）。"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是企业知识库助手。只依据【参考资料】回答，资料里没有的内容，明确说'资料中未找到'，不要编造。"),
        ("human", "【参考资料】\n{context}\n\n【问题】\n{question}"),
    ])
    return prompt | get_llm()


def _prepare(question: str, k: int | None = None) -> tuple[list[Document], str, object]:
    """检索 + 拼上下文 + 建链 —— 三个入口共用，消除重复。"""
    docs = retrieve(question, k=k)
    context = "\n\n".join(d.page_content for d in docs)
    return docs, context, _build_chain()


def ask(question: str) -> str:
    """一次性返回完整答案；检索为空时直接拒答（不给模型编造的机会）。"""
    docs, context, chain = _prepare(question)
    if not docs:
        return "资料中未找到相关内容。"
    return chain.invoke({"context": context, "question": question}).content


def ask_stream(question: str):
    """逐块产出答案文本（生成器）——调用方决定拿去打印、写 SSE 还是别的。"""
    docs, context, chain = _prepare(question)
    if not docs:
        yield "资料中未找到相关内容。"
        return
    for chunk in chain.stream({"context": context, "question": question}):
        if chunk.content:
            yield chunk.content


if __name__ == "__main__":
    for text in ask_stream("年假有几天？"):
        print(text, end="", flush=True)
