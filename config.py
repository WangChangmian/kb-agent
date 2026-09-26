"""配置层：企业标准 —— 代码里不写死任何 key/路径，一切从环境变量读。

为什么单独一层？
- 本地/测试/生产用不同 .env，代码零改动
- 面试官问「你的 key 放哪？」答：pydantic-settings 从环境变量注入，.env 不进 git

【关键设计】所有路径都以项目根为基准（BASE_DIR），不依赖"在哪个目录运行"：
- .env 用绝对路径加载，任何目录下都能读到
- 向量库路径解析成绝对路径，永远指向同一个位置
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：以 config.py 所在位置为准，CWD 无关
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # .env 用绝对路径加载，避免"在不同目录运行就读不到"的问题
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )

    # ---- 对话模型（真实值在 .env，这里只是兜底占位）----
    llm_api_key: str = "sk-xxx"                      # 生产必须环境变量注入
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_temperature: float = 0.0                     # 检索问答类任务低温，少胡编

    # ---- Embeddings（真实值在 .env）----
    # 真实坑：DeepSeek 官方【没有】embeddings 接口！chat 与 embeddings 可以不同厂商
    # provider 三选一：openai / siliconflow / bge
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""                      # 留空则复用 llm_api_key
    embedding_base_url: str = ""                     # siliconflow 填；OpenAI 官方留空

    # ---- 向量库 后端 chroma|milvus ----
    vector_db_dir: str = "./data/chroma"
    vector_backend: str = "chroma"
    milvus_uri: str = "http://127.0.0.1:19530"

    # ---- 检索参数（M1 课我们一起调）----
    retriever_top_k: int = 4
    retriever_score_threshold: float = 0.2

    @property
    def vector_db_dir_abs(self) -> str:
        """把相对路径解析成绝对路径（以项目根为基准），彻底摆脱 CWD 依赖。"""
        p = Path(self.vector_db_dir)
        return str(p if p.is_absolute() else BASE_DIR / p)


# 全局单例：全项目统一从这里读配置
settings = Settings()
