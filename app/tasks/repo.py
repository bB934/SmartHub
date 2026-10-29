"""任务状态读写：ingest_task 表的唯一入口，避免各调用点各写一套 SQL。"""

from app.db.mysql import SessionLocal
from app.models.doc import IngestTask


def get_or_create(doc_id: int) -> IngestTask:
    with SessionLocal() as session:
        task = session.query(IngestTask).filter(IngestTask.doc_id == doc_id).first()
        if task is None:
            task = IngestTask(doc_id=doc_id, stage="PARSE", retry_count=0)
            session.add(task)
            session.commit()
        return task


def get(doc_id: int) -> IngestTask | None:
    with SessionLocal() as session:
        return session.query(IngestTask).filter(IngestTask.doc_id == doc_id).first()


def set_stage(doc_id: int, stage: str) -> None:
    with SessionLocal() as session:
        session.query(IngestTask).filter(IngestTask.doc_id == doc_id).update(
            {"stage": stage, "error_msg": None}
        )
        session.commit()


def fail(doc_id: int, stage: str, error_msg: str) -> None:
    with SessionLocal() as session:
        session.query(IngestTask).filter(IngestTask.doc_id == doc_id).update(
            {
                "stage": stage,
                "retry_count": IngestTask.retry_count + 1,
                "error_msg": error_msg[:1000],
            }
        )
        session.commit()


def reset(doc_id: int) -> None:
    """重建索引时把任务状态拨回起点，否则断点续跑会直接跳到 DONE。"""
    with SessionLocal() as session:
        session.query(IngestTask).filter(IngestTask.doc_id == doc_id).update(
            {"stage": "PARSE", "retry_count": 0, "error_msg": None}
        )
        session.commit()
