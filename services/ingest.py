"""文档入库服务（M1 课一起实现）。

链路（离线阶段，一次做好，反复查询）：
    加载文档 -> 清洗 -> 分块 -> 向量化 -> 写入向量库

# TODO（下次课填）：
1. 用 LangChain 的 loader 加载文档（txt / md / pdf）
2. 选分块器 + 定参数：chunk_size 与 overlap 怎么权衡？（M1_lesson.md 第2节）
3. 调 get_vector_store() 写入
4. 打印入库统计（多少块、耗时）—— 企业里还要写日志
"""
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from services.vector_store import get_vector_store

def ingest(doc_path: str)->str:
    loader = TextLoader(doc_path,encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
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