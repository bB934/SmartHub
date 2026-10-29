"""SSE 流式问答：sources → token* → done。

要点：
- X-Accel-Buffering: no 必须有，否则 Nginx 会缓冲，SSE 变成一次性返回；
- 没配大模型密钥时退回“原文摘录”，绝不编造；
- 语义缓存只在配置了大模型时写入，命中缓存直接秒回。
"""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.context import RequestContext, current_ctx
from app.db.mysql import SessionLocal
from app.llm import cache
from app.llm.gateway import gateway
from app.llm.prompt import build_prompt
from app.retrieve.reranker import rerank
from app.retrieve.retriever import hybrid_recall
from app.schemas import ChatRequest

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def extractive_answer(chunks: list[dict]) -> str:
    """没有模型时只摘录检索到的原文，明确告诉用户这是摘录而不是生成。"""
    parts = ["（当前未配置大模型密钥，以下为知识库原文摘录）"]
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}] {chunk['text'].strip()}")
    return "\n\n".join(parts)


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, ctx: RequestContext = Depends(current_ctx)):
    async def gen() -> AsyncIterator[str]:
        try:
            cached = await cache.lookup(req.question, ctx)
        except Exception as e:      # 典型场景：还没填 OpenRouter Key，向量化直接失败
            yield sse("error", {"message": str(e)})
            yield sse("done", {"cached": False, "recalled": 0, "reranked": 0})
            return
        if cached:
            # 拒答不该走缓存：旧版本把它也写进去了，命中后会丢掉来源，按未命中重跑
            if "知识库中没有相关内容" in cached:
                cached = None
            else:
                yield sse("sources", [])
                yield sse("token", {"content": cached})
                yield sse("done", {"cached": True, "recalled": 0, "reranked": 0, "no_answer": False})
                return

        with SessionLocal() as session:
            cands = await hybrid_recall(req.question, ctx, session, req.topk)
        top = rerank(req.question, cands, settings.rerank_topn)
        refs = [
            {
                "idx": i + 1,
                "doc_id": c["doc_id"],
                "heading": c.get("heading") or "",
                "snippet": c["text"][:200],
            }
            for i, c in enumerate(top)
        ]
        yield sse("sources", refs)

        if not top:
            yield sse("token", {"content": "知识库中没有相关内容。"})
            yield sse("done", {"cached": False, "recalled": len(cands), "reranked": 0, "no_answer": True})
            return

        if not gateway.enabled:
            yield sse("token", {"content": extractive_answer(top)})
            yield sse("done", {"cached": False, "recalled": len(cands), "reranked": len(top)})
            return

        prompt = build_prompt(req.question, top)
        answer_parts: list[str] = []
        try:
            async for token in gateway.astream(prompt):
                answer_parts.append(token)
                yield sse("token", {"content": token})
        except Exception as e:      # 两路模型都挂 → 明确报错，不返回空白
            yield sse("error", {"message": f"模型调用失败：{e}"})
            yield sse("done", {"cached": False, "recalled": len(cands), "reranked": len(top)})
            return

        answer = "".join(answer_parts).strip()
        # 模型选择了拒答：此时 sources 只是“检索到的最相似片段”，并未被引用，
        # 前端据此把标题从“引用来源”改成提示，避免用户以为资料里有答案
        no_answer = "知识库中没有相关内容" in answer
        if answer and not no_answer:
            try:
                await cache.store(req.question, ctx, answer)
            except Exception:       # 缓存是加分项，失败不影响主流程
                logger.warning("语义缓存写入失败", exc_info=True)
        yield sse("done", {"cached": False, "recalled": len(cands), "reranked": len(top), "no_answer": no_answer})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
