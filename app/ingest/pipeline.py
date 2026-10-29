"""入库流水线：PARSE → SPLIT → EMBED → INDEX → SWITCH → DONE。

每个阶段都把中间产物落盘到 data/work/{doc_id}/，所以任务中断后可以从当前 stage 续跑，
不用把已经解析/已经向量化的内容重做一遍。
"""

import json
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.es import delete_doc as es_delete_doc
from app.db.es import delete_version as es_delete_version
from app.db.es import index_chunks
from app.db.es import update_status as es_update_status
from app.db.milvus import get_client
from app.db.mysql import SessionLocal
from app.ingest.parser import parse_file
from app.ingest.splitter import split_markdown
from app.models.doc import Doc
from app.rag.embed import embed_texts_sync

MILVUS_QUERY_LIMIT = 16384


def work_dir(doc_id: int) -> Path:
    return Path(settings.data_dir) / "work" / str(doc_id)


def object_path(object_key: str) -> Path:
    return Path(settings.data_dir) / "objects" / object_key


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _milvus_set_status(
    doc_id: int,
    to_status: int,
    from_status: int | None = None,
    index_version: int | None = None,
) -> int:
    """Milvus 没有 update 接口，只能 query 出整行再 upsert（pk 不变，chunk_id 也不变）。"""
    client = get_client()
    expr = f"doc_id == {doc_id}"
    if from_status is not None:
        expr += f" and index_status == {from_status}"
    if index_version is not None:
        expr += f" and index_version == {index_version}"

    rows = client.query(
        collection_name=settings.milvus_collection,
        filter=expr,
        output_fields=["*"],
        limit=MILVUS_QUERY_LIMIT,
    )
    if not rows:
        return 0
    for row in rows:
        row["index_status"] = to_status
    client.upsert(collection_name=settings.milvus_collection, data=rows)
    client.flush(settings.milvus_collection)
    return len(rows)


def _load_doc(session: Session, doc_id: int) -> Doc:
    doc = session.get(Doc, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在：doc_id={doc_id}")
    return doc


def stage_parse(doc_id: int) -> None:
    with SessionLocal() as session:
        doc = _load_doc(session, doc_id)
        if not doc.object_key:
            raise ValueError("文档缺少原文 object_key")
        text = parse_file(str(object_path(doc.object_key)))
    wd = work_dir(doc_id)
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "parsed.txt").write_text(text, encoding="utf-8")


def stage_split(doc_id: int) -> None:
    wd = work_dir(doc_id)
    text = (wd / "parsed.txt").read_text(encoding="utf-8")
    chunks = split_markdown(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("切片结果为空，检查原文是否有文本内容")
    (wd / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )


def stage_embed(doc_id: int) -> None:
    wd = work_dir(doc_id)
    chunks = _read_json(wd / "chunks.json")
    vectors = embed_texts_sync([c["text"] for c in chunks])
    for chunk, vec in zip(chunks, vectors, strict=True):
        chunk["embedding"] = vec
    (wd / "embedded.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )


def stage_index(doc_id: int) -> None:
    wd = work_dir(doc_id)
    chunks = _read_json(wd / "embedded.json")
    with SessionLocal() as session:
        doc = _load_doc(session, doc_id)
        # 幂等：INDEX 前先清掉本版本的 staging 残留（INDEX 成功后 SWITCH 失败会重跑本阶段）
        get_client().delete(
            collection_name=settings.milvus_collection,
            filter=(
                f"doc_id == {doc.id} and index_version == {doc.index_version} "
                f"and index_status == 0"
            ),
        )
        es_delete_version(doc.id, doc.index_version, 0)
        rows = [
            {
                "tenant_id": doc.tenant_id,
                "space_id": doc.space_id,
                "doc_id": doc.id,
                "chunk_id": c["chunk_id"],
                "heading": c["heading"][:160],
                "text": c["text"][:2000],
                "visibility": doc.visibility,
                "index_status": 0,          # 先写 staging，SWITCH 阶段才生效
                "index_version": doc.index_version,
                "embedding": c["embedding"],
            }
            for c in chunks
        ]
        client = get_client()
        client.insert(collection_name=settings.milvus_collection, data=rows)
        client.flush(settings.milvus_collection)   # 不 flush 查不到刚写的数据
        index_chunks([{k: v for k, v in row.items() if k != "embedding"} for row in rows])


def stage_switch(session: Session, doc: Doc) -> int:
    """蓝绿切换：旧版本整体置废弃，新版本整体置生效，检索表达式恒带 index_status==1。"""
    new_version = doc.index_version
    _milvus_set_status(doc.id, to_status=2, from_status=1)
    es_update_status(doc.id, to_status=2, from_status=1)
    activated = _milvus_set_status(
        doc.id, to_status=1, from_status=0, index_version=new_version
    )
    es_update_status(doc.id, to_status=1, from_status=0, index_version=new_version)

    doc.index_status = 1
    doc.chunk_count = activated
    session.commit()
    return activated


def run_stage(stage: str, doc_id: int) -> None:
    """执行单个阶段。DONE 是终态，只落状态。"""
    if stage == "PARSE":
        stage_parse(doc_id)
    elif stage == "SPLIT":
        stage_split(doc_id)
    elif stage == "EMBED":
        stage_embed(doc_id)
    elif stage == "INDEX":
        stage_index(doc_id)
    elif stage == "SWITCH":
        with SessionLocal() as session:
            stage_switch(session, _load_doc(session, doc_id))
    elif stage == "DONE":
        pass
    else:
        raise ValueError(f"未知阶段：{stage}")


def purge_doc_index(doc_id: int) -> None:
    """删除文档全部索引与中间产物，用于删除文档 / 重建。"""
    get_client().delete(collection_name=settings.milvus_collection, filter=f"doc_id == {doc_id}")
    get_client().flush(settings.milvus_collection)
    es_delete_doc(doc_id)
    shutil.rmtree(work_dir(doc_id), ignore_errors=True)
