"""Elasticsearch 客户端与 kb_chunk 索引（中文用 IK 分词）。

索引结构与 Milvus 集合对齐：两路召回按 chunk_id 融合，所以 chunk_id 必须一致。
"""

from elasticsearch import Elasticsearch, NotFoundError, helpers

from app.core.config import settings

INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "tenant_id": {"type": "long"},
            "space_id": {"type": "long"},
            "doc_id": {"type": "long"},
            "heading": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            "text": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            "index_status": {"type": "integer"},
            "index_version": {"type": "integer"},
        }
    },
}

_client: Elasticsearch | None = None


def get_es() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(hosts=[settings.es_url], request_timeout=30)
    return _client


def ensure_index() -> bool:
    """幂等创建索引，返回是否本次新建。"""
    es = get_es()
    if es.indices.exists(index=settings.es_index):
        return False
    es.indices.create(index=settings.es_index, **INDEX_BODY)
    return True


def index_chunks(rows: list[dict]) -> None:
    """批量写入分片。chunk_id 作为 _id，重复写入是覆盖而不是产生重复。"""
    if not rows:
        return
    actions = [
        {"_index": settings.es_index, "_id": row["chunk_id"], "_source": row}
        for row in rows
    ]
    helpers.bulk(get_es(), actions)
    get_es().indices.refresh(index=settings.es_index)


def update_status(
    doc_id: int,
    to_status: int,
    from_status: int | None = None,
    index_version: int | None = None,
) -> int:
    """按条件批量改 index_status，用于蓝绿切换。返回受影响文档数。"""
    filters: list[dict] = [{"term": {"doc_id": doc_id}}]
    if from_status is not None:
        filters.append({"term": {"index_status": from_status}})
    if index_version is not None:
        filters.append({"term": {"index_version": index_version}})
    resp = get_es().update_by_query(
        index=settings.es_index,
        query={"bool": {"filter": filters}},
        script={
            "source": "ctx._source.index_status = params.to",
            "params": {"to": to_status},
        },
        refresh=True,
    )
    return int(resp.get("updated", 0))


def delete_version(doc_id: int, index_version: int, index_status: int) -> int:
    """删除某文档某版本、某状态的分片，用于 INDEX 阶段重跑时先清掉上一次的残留。"""
    try:
        resp = get_es().delete_by_query(
            index=settings.es_index,
            query={
                "bool": {
                    "filter": [
                        {"term": {"doc_id": doc_id}},
                        {"term": {"index_version": index_version}},
                        {"term": {"index_status": index_status}},
                    ]
                }
            },
            refresh=True,
        )
    except NotFoundError:
        return 0
    return int(resp.get("deleted", 0))


def delete_doc(doc_id: int) -> int:
    """删除某文档的全部分片。文档不存在时返回 0。"""
    try:
        resp = get_es().delete_by_query(
            index=settings.es_index,
            query={"term": {"doc_id": doc_id}},
            refresh=True,
        )
    except NotFoundError:
        return 0
    return int(resp.get("deleted", 0))
