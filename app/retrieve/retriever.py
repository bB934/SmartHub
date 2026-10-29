"""检索：向量召回 + BM25 召回，RRF 融合，权限过滤下推。"""

from elasticsearch import NotFoundError
from sqlalchemy.orm import Session

from app.core.acl import authorized_doc_ids
from app.core.config import settings
from app.db.es import get_es
from app.db.milvus import get_client
from app.rag.embed import embed_query
from app.retrieve.fusion import rrf_fuse


async def hybrid_recall(q: str, ctx, session: Session, topk: int | None = None) -> list[dict]:
    topk = topk or settings.recall_topk
    authorized = authorized_doc_ids(ctx, session)
    if not authorized:
        return []
    allowed = set(authorized)

    # 路 1：Milvus 向量召回，权限过滤下推
    vec = await embed_query(q)
    expr = (
        f"tenant_id == {ctx.tenant_id} and index_status == 1 "
        f"and doc_id in [{','.join(map(str, authorized))}]"
    )
    v_hits = get_client().search(
        collection_name=settings.milvus_collection,
        data=[vec],
        filter=expr,
        limit=topk,
        search_params={"metric_type": "COSINE", "params": {"ef": 64}},
        output_fields=["chunk_id", "doc_id", "heading", "text", "tenant_id", "space_id"],
    )[0]
    vec_road = [dict(hit["entity"], score=hit["distance"]) for hit in v_hits]

    # 路 2：ES BM25 关键词召回（中文用 IK 分词）
    try:
        k_hits = get_es().search(
            index=settings.es_index,
            size=topk,
            query={
                "bool": {
                    "must": [
                        {"multi_match": {"query": q, "fields": ["text^3", "heading^2"]}}
                    ],
                    "filter": [
                        {"terms": {"doc_id": authorized}},
                        {"term": {"tenant_id": ctx.tenant_id}},
                        {"term": {"index_status": 1}},
                    ],
                }
            },
        )["hits"]["hits"]
    except NotFoundError:
        k_hits = []
    bm25_road = [dict(hit["_source"], score=hit["_score"]) for hit in k_hits]

    fused = rrf_fuse([vec_road, bm25_road])
    # 双保险：融合结果再按权限集合筛一遍，防止过滤表达式拼错导致越权
    return [c for c in fused if c.get("doc_id") in allowed]
