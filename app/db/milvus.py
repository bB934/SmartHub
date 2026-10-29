"""Milvus 客户端单例与 kb_chunk 集合定义。

放在 app/db/ 下，与后续的 mysql.py / redis.py 平级。
建集合的逻辑**不要写在 import 期**，统一由 ensure_collection() 触发，保证幂等、可重复执行。

用法：
    python -m app.db.milvus            # 不存在则创建，已存在则跳过
    python -m app.db.milvus --drop     # 删除重建（换 embedding 模型 / 改维度时必须用）
"""
from typing import cast

from pymilvus import DataType, MilvusClient

from app.core.config import settings

# ---- 字段名常量：写数据和检索表达式都依赖这些名字，集中在这里避免拼错 ----
F_PK = "pk"
F_TENANT = "tenant_id"
F_SPACE = "space_id"
F_DOC = "doc_id"
F_CHUNK = "chunk_id"
F_HEADING = "heading"
F_TEXT = "text"
F_VISIBILITY = "visibility"
F_INDEX_STATUS = "index_status"
F_INDEX_VERSION = "index_version"
F_EMBEDDING = "embedding"

# 向量维度唯一来源是 settings.embed_dim（nvidia/nemotron-3.5-embed-1b:free 输出 2048 维）。
# 换模型且维度变化时必须重建集合：python -m app.db.milvus --drop
EMBED_DIM = settings.embed_dim

_client: MilvusClient | None = None


def get_client() -> MilvusClient:
    """全局复用同一个客户端。MilvusClient 内部维护连接池，每次 new 一个会浪费连接。"""
    global _client
    if _client is None:
        _client = MilvusClient(uri=settings.milvus_uri)
    return _client


def build_schema():
    client = get_client()
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field(F_PK, DataType.INT64, is_primary=True, auto_id=True)
    # 分区键：同一个 tenant_id 的数据落在同一物理分区，检索时按租户裁剪扫描范围
    schema.add_field(F_TENANT, DataType.INT64, is_partition_key=True)
    schema.add_field(F_SPACE, DataType.INT64)
    schema.add_field(F_DOC, DataType.INT64)
    # VARCHAR 的 max_length 单位是**字节**不是字符：中文 UTF-8 占 3 字节
    schema.add_field(F_CHUNK, DataType.VARCHAR, max_length=64)
    schema.add_field(F_HEADING, DataType.VARCHAR, max_length=512)
    schema.add_field(F_TEXT, DataType.VARCHAR, max_length=8192)   # ≈ 2730 个汉字，500 字切片足够
    schema.add_field(F_VISIBILITY, DataType.INT8)                  # 0 空间 1 指定组 2 私有
    schema.add_field(F_INDEX_STATUS, DataType.INT8)                # 0 待切 1 生效 2 废弃
    schema.add_field(F_INDEX_VERSION, DataType.INT32)
    schema.add_field(F_EMBEDDING, DataType.FLOAT_VECTOR, dim=EMBED_DIM)
    return schema


def build_index_params():
    client = get_client()
    idx = client.prepare_index_params()
    idx.add_index(
        field_name=F_EMBEDDING,
        index_type="HNSW",
        metric_type="COSINE",          # COSINE 相似度范围 [-1, 1]，越大越相关（与 L2 相反）
        params={"M": 16, "efConstruction": 200},
    )
    return idx


def ensure_collection(collection: str | None = None, drop: bool = False) -> bool:
    """幂等地保证集合存在。

    :return: True = 本次新建；False = 已存在，未改动
    """
    client = get_client()
    name = collection or settings.milvus_collection

    if client.has_collection(name):
        if not drop:
            return False
        client.drop_collection(name)

    client.create_collection(
        collection_name=name,
        schema=build_schema(),
        index_params=build_index_params(),
    )
    # 不 load 的集合搜不到数据；load 是内存加载，幂等但会阻塞，启动期调一次即可
    client.load_collection(name)
    return True


if __name__ == "__main__":
    import sys

    name = settings.milvus_collection
    created = ensure_collection(drop="--drop" in sys.argv)
    state = get_client().get_load_state(name)
    print(f"{'[新建]' if created else '[已存在]'} {name} | load_state={state}")
    # pymilvus 的 describe_collection 桩标注成 async，运行时其实是同步返回 dict
    info = cast(dict, get_client().describe_collection(name))
    print("字段:", [f["name"] for f in info["fields"]])
