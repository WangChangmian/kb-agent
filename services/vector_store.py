#使用milvus三件套
from langchain_chroma import Chroma

from config import settings


def get_embeddings():
    """Embeddings 工厂：按 .env 的 EMBEDDING_PROVIDER 切换方案。

    真实坑：DeepSeek 官方目前【没有】embeddings 接口！
    embeddings 和 chat 模型可以来自不同厂商，这是行业常规做法：
    - openai      : OpenAI text-embedding-3-small（需 OpenAI key）
    - siliconflow : 硅基流动，OpenAI 兼容协议，国内直连（只有 DeepSeek key 时首选）
    - bge         : 本地 BAAI/bge-small-zh-v1.5，免费离线（需 pip install langchain-huggingface）
    """
    provider = settings.embedding_provider.lower()
    api_key = settings.embedding_api_key or settings.llm_api_key   # 留空复用 chat 的 key

    if provider == "bge":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=settings.embedding_model or "BAAI/bge-small-zh-v1.5")

    # openai 与 siliconflow 都是 OpenAI 兼容协议，只差 base_url 和 key
    # langchain-openai 0.3+ 的正规写法：用 init_embeddings 统一初始化
    # （OpenAIEmbeddings 直接传 provider 会把参数漏进 API 调用导致 TypeError）
    try:
        from langchain.embeddings import init_embeddings
    except ImportError:                                  # 跨版本兜底
        from langchain_core.embeddings import init_embeddings

    return init_embeddings(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=settings.embedding_base_url or None,
        provider="openai",   # 硅基流动走 OpenAI 兼容协议
    )


def get_vector_store(collection: str = "kb_docs") :
    """获取（不存在则创建）向量库实例。

    注意：persist_directory 用 vector_db_dir_abs（绝对路径），
    保证不管在哪运行，读写的都是同一个库。
    """
    if settings.vector_backend.lower() == "milvus":
        from langchain_milvus import Milvus

        # 从 settings.milvus_uri 里拆出 host 和 port（兼容你 .env 里写的格式）
        # 假设 .env 里 MILVUS_URI=127.0.0.1:19530 或 http://127.0.0.1:19530
        raw = settings.milvus_uri.replace("http://", "").replace("https://", "")
        host, port = raw.split(":")

        return Milvus(
            embedding_function=get_embeddings(),
            collection_name=collection,
            connection_args={"host": host, "port": port},  # 用 host+port，不用 uri
            index_params={"metric_type": "COSINE", "index_type": "AUTOINDEX", "params": {}},
        )

    return Chroma(
        collection_name=collection,
        embedding_function=get_embeddings(),
        persist_directory=settings.vector_db_dir_abs,
        collection_metadata={"hnsw:space": "cosine"},   # 余弦相似度：相关度分数落在 [0,1]，阈值才可靠
    )
