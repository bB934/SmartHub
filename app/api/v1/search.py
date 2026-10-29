"""检索调试接口：直接返回双路召回 + RRF 融合后的候选，便于排查“答不准”是哪一步的问题。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.context import RequestContext, current_ctx
from app.db.mysql import get_db
from app.models.doc import Doc
from app.retrieve.retriever import hybrid_recall
from app.schemas import SearchRequest

router = APIRouter(tags=["search"])


@router.post("/search")
async def search(
    req: SearchRequest,
    ctx: RequestContext = Depends(current_ctx),
    session: Session = Depends(get_db),
):
    try:
        cands = await hybrid_recall(req.query, ctx, session, req.topk)
    except RuntimeError as e:      # 典型场景：还没填 OpenRouter Key，查询向量化失败
        raise HTTPException(503, str(e)) from e
    titles = {
        doc.id: doc.title
        for doc in session.query(Doc).filter(Doc.id.in_([c["doc_id"] for c in cands]))
    } if cands else {}
    items = [
        {
            "chunk_id": c.get("chunk_id"),
            "doc_id": c["doc_id"],
            "doc_title": titles.get(c["doc_id"], ""),
            "heading": c.get("heading") or "",
            "text": c.get("text", ""),
            "score": round(c.get("rrf", 0.0), 6),
        }
        for c in cands
    ]
    return {"query": req.query, "total": len(items), "items": items}
