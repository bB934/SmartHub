"""精排：调 OpenRouter 的 rerank 接口（nvidia/nemotron-3.5-rerank-8b:free）。

OpenRouter 的 rerank 请求/响应与 Cohere 一致：
    请求 {model, query, documents[], top_n}
    响应 {results: [{index, relevance_score}]}
Key 未填或调用失败时退回按 RRF 分截断，保证问答不至于整条链路都挂掉。
"""

import logging

import httpx

from app.core.config import openrouter_ready, settings

logger = logging.getLogger(__name__)


def _fallback(cands: list[dict], topn: int) -> list[dict]:
    return sorted(cands, key=lambda c: c.get("rrf", 0.0), reverse=True)[:topn]


def rerank(q: str, cands: list[dict], topn: int = 5) -> list[dict]:
    if not cands:
        return []
    if not openrouter_ready():
        return _fallback(cands, topn)

    try:
        resp = httpx.post(
            f"{settings.openrouter_base_url}/rerank",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
            json={
                "model": settings.rerank_model,
                "query": q,
                "documents": [c["text"] for c in cands],
                "top_n": topn,
            },
            timeout=60,
        )
        resp.raise_for_status()
        results = resp.json()["results"]
    except Exception:
        logger.warning("rerank 调用失败，退回 RRF 排序", exc_info=True)
        return _fallback(cands, topn)

    ranked = [
        cands[r["index"]] | {"rerank_score": r["relevance_score"]}
        for r in results
        if 0 <= r["index"] < len(cands)
    ]
    return ranked[:topn]
