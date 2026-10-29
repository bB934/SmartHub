"""应用配置：地址、密钥、阈值全部来自环境变量或 .env，代码里不写死。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：.env 用绝对路径，从任何工作目录启动（uvicorn / celery / IDE）都能读到
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",      # 环境里无关变量不该导致启动失败
    )

    # ---- 存储 ----
    mysql_dsn: str = "mysql+pymysql://root:rag123@127.0.0.1:3307/rag"   # 本机 3306 被占用，容器映射 3307
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "kb_chunk"
    qa_cache_collection: str = "qa_cache"
    es_url: str = "http://localhost:9200"
    es_index: str = "kb_chunk"
    redis_url: str = "redis://localhost:6380/0"          # 本机 6379 被占用，容器映射 6380
    data_dir: str = "data"                                # 原文与流水线中间产物

    # ---- OpenRouter：embed / llm / rerank 三处共用同一个 Key ----
    # Key 写在项目根目录 .env 的 OPENROUTER_API_KEY=... 里（推荐），
    # 不想用 .env 也可把下面的空串直接改成你的 Key，两者都留空则相关能力自动降级。
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = "http://localhost:8000"     # HTTP-Referer，用于 OpenRouter 用量统计
    openrouter_app_name: str = "SmartHub RAG"             # X-Title

    embed_model: str = "nvidia/nemotron-3.5-embed-1b:free"
    embed_dim: int = 2048                                 # 必须与模型输出维度一致，改这里要重建 Milvus 集合
    llm_model: str = "recursive/flint-v1.0:free"
    rerank_model: str = "nvidia/nemotron-3.5-rerank-8b:free"

    # ---- 检索参数 ----
    chunk_size: int = 500
    chunk_overlap: int = 100
    recall_topk: int = 50
    rerank_topn: int = 5
    embed_batch: int = 32
    cache_score: float = 0.95                             # 语义缓存命中阈值（COSINE）

    # ---- 运行方式 ----
    use_celery: bool = False                              # False：上传后由 BackgroundTasks 入库，单进程即可跑通
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()


def openrouter_ready() -> bool:
    """空值，或仍是文档里的占位符（YOUR_...）时视为未配置。"""
    key = settings.openrouter_api_key.strip()
    return bool(key) and not key.startswith("YOUR_")
