"""文本向量化：走 OpenRouter 的 nvidia/nemotron-3.5-embed-1b:free（输出 2048 维）。

为什么走 HTTP 而不是本地加载模型：
    本地 encode() 是同步 CPU 密集调用，放进 async def 会阻塞整个事件循环；
    OpenRouter 的 /embeddings 接口天然异步，也不用在本机装 torch。

维度必须与 Milvus 集合一致（settings.embed_dim = EMBED_DIM = 2048），
换模型且维度变化后要重建集合：python -m app.db.milvus --drop
"""

import httpx

from app.core.config import openrouter_ready, settings
from app.db.milvus import EMBED_DIM

_async_client: httpx.AsyncClient | None = None
_sync_client: httpx.Client | None = None


def _async_http() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(timeout=120)
    return _async_client


def _sync_http() -> httpx.Client:
    """同步客户端：给 CLI / Celery worker 这类非 async 场景用。"""
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(timeout=120)
    return _sync_client


def _headers() -> dict[str, str]:
    if not openrouter_ready():
        raise RuntimeError(
            "未配置 OpenRouter API Key：请在项目根目录的 .env 里填写 "
            "OPENROUTER_API_KEY=sk-or-v1-...（或设置同名环境变量）"
        )
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.openrouter_app_url,
        "X-Title": settings.openrouter_app_name,
    }


def _payload(batch: list[str]) -> dict:
    return {"model": settings.embed_model, "input": batch, "encoding_format": "float"}


def _parse(payload: dict) -> list[list[float]]:
    """按 index 排序，保证返回顺序与入参顺序一致（并发返回时顺序不保证）。"""
    rows = sorted(payload["data"], key=lambda d: d.get("index", 0))
    return [_check(row["embedding"]) for row in rows]


def _check(vec: list[float]) -> list[float]:
    if len(vec) != EMBED_DIM:
        raise ValueError(
            f"向量维度不符：期望 {EMBED_DIM}，实际 {len(vec)}。"
            f"检查 {settings.embed_model} 的实际输出维度，并同步修改 settings.embed_dim"
        )
    return vec


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化（异步）。按 embed_batch 分片，避免单次请求过大。"""
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), settings.embed_batch):
        batch = texts[i:i + settings.embed_batch]
        r = await _async_http().post(
            f"{settings.openrouter_base_url}/embeddings",
            headers=_headers(),
            json=_payload(batch),
        )
        r.raise_for_status()
        out.extend(_parse(r.json()))
    return out


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """批量向量化（同步）。建库流水线用这个。"""
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), settings.embed_batch):
        batch = texts[i:i + settings.embed_batch]
        r = _sync_http().post(
            f"{settings.openrouter_base_url}/embeddings",
            headers=_headers(),
            json=_payload(batch),
        )
        r.raise_for_status()
        out.extend(_parse(r.json()))
    return out


async def embed_query(text: str) -> list[float]:
    """单条查询向量。文档侧和查询侧必须用同一个模型、同一套处理，否则相似度没有可比性。"""
    return (await embed_texts([text]))[0]


if __name__ == "__main__":
    vecs = embed_texts_sync(["企业级知识库的权限模型", "决策树如何选择分裂特征"])
    print(f"条数={len(vecs)} 维度={len(vecs[0])} 模型={settings.embed_model}")
