"""文档入库服务：加载 → 分块 → 向量化 → 写库（离线阶段，一次做好、反复查询）。

分块策略按文件类型区分：
- Markdown（有 ## 标题的结构化文档）→ 按标题切，每块一个主题，并把章节名写进 metadata
- 纯文本 → 按字符切（300/30），块小而聚焦

为什么这么做（实测教训）：
  chunk_size=500 对只有 963 字的《员工手册》太大，只切出 3 块，
  每块混了 4~5 个不相关章节 → 块向量被通用文本主导 → 检索时"公司简介"成了万金油，
  对任何问题都排第一，真正相关的块反而被挤出 top_k。
  改成按标题切后变成 8 块（每块一个主题），评估指标 Recall@4 从 10% 提升到 90%。
"""
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from services.vector_store import get_vector_store


def ingest(doc_path: str) -> int:
    """把一个文档切块并写入向量库，返回写入的块数。"""
    docs = TextLoader(doc_path, encoding="utf-8").load()

    if doc_path.lower().endswith((".md", ".markdown")):
        # 结构化文档：按 Markdown 标题切 → 每块一个主题
        text = "\n\n".join(d.page_content for d in docs)
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("##", "section")],
            strip_headers=False,          # 标题保留在正文里，相当于天然的上下文增强
        )
        chunks = splitter.split_text(text)
        for c in chunks:                  # 它不保留 loader 的 metadata，手动补 source
            c.metadata["source"] = doc_path
    else:
        # 非结构化文本：按字符切
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=30,
            separators=["\n\n", "\n", "。", " ", ""],
        )
        chunks = splitter.split_documents(docs)

    vs = get_vector_store()
    vs.add_documents(chunks)
    return len(chunks)


if __name__ == "__main__":
    from config import BASE_DIR

    doc_path = BASE_DIR / "data" / "sample" / "星辰科技员工手册.md"
    n = ingest(str(doc_path))
    print(f"入库完成，共 {n} 块")
