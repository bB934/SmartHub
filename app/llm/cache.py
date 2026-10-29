"""语义缓存：相似问题直接复用上次答案，命中率通常 15~30%，是降本最省事的一招。"""
from pymilvus import DataType

from app.core.config import settings
from app.db.milvus import get_client
from app.rag.embed import EMBED_DIM, embed_query

_name = settings.qa_cache_collection
_ready = False


def ensure_collection() -> bool:
    """qa_cache 是独立集合，首次用到时创建，返回是否本次新建。"""
    global _ready
    client = get_client()
    if _ready or client.has_collection(_name):
        _ready = True
        return False

    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("pk", DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field("tenant_id", DataType.INT64, is_partition_key=True)
    schema.add_field("question", DataType.VARCHAR, max_length=8192)
    schema.add_field("answer", DataType.VARCHAR, max_length=8192)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBED_DIM)

    idx = client.prepare_index_params()
    idx.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(collection_name=_name, schema=schema, index_params=idx)
    client.load_collection(_name)
    _ready = True
    return True


async def lookup(q: str, ctx) -> str | None:
    ensure_collection()
    vec = await embed_query(q)
    hits = get_client().search(
        collection_name=_name,
        data=[vec],
        limit=1,
        filter=f"tenant_id == {ctx.tenant_id}",
        search_params={"metric_type": "COSINE", "params": {"ef": 64}},
        output_fields=["answer"],
    )
    if hits and hits[0] and hits[0][0]["distance"] >= settings.cache_score:
        return hits[0][0]["entity"]["answer"]
    return None


async def store(q: str, ctx, answer: str) -> None:
    ensure_collection()
    vec = await embed_query(q)
    get_client().insert(
        collection_name=_name,
        data=[
            {
                "tenant_id": ctx.tenant_id,
                "question": q[:2000],
                "answer": answer[:2000],
                "embedding": vec,
            }
        ],
    )
    get_client().flush(_name)
