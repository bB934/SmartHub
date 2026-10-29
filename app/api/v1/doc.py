"""文档管理：上传 → 异步入库 → 列表 → 重建 → 删除。"""

import hashlib
import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.core.context import RequestContext, current_ctx
from app.db.mysql import get_db
from app.ingest.pipeline import object_path, purge_doc_index, work_dir
from app.models.doc import Doc, IngestTask
from app.schemas import DocOut, TaskOut
from app.tasks import repo as task_repo
from app.tasks.ingest_task import enqueue_ingest

router = APIRouter(prefix="/doc", tags=["doc"])

ALLOWED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt", ".docx"}


def _get_doc(session: Session, doc_id: int, ctx: RequestContext) -> Doc:
    doc = session.get(Doc, doc_id)
    if doc is None or doc.tenant_id != ctx.tenant_id:
        raise HTTPException(404, f"文档不存在：{doc_id}")
    return doc


@router.post("/upload", response_model=DocOut, status_code=201)
async def upload_doc(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    visibility: int = Form(0),
    groups: str = Form(""),
    ctx: RequestContext = Depends(current_ctx),
    session: Session = Depends(get_db),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"不支持的格式：{suffix or '无扩展名'}")
    if visibility not in (0, 1, 2):
        raise HTTPException(400, "visibility 只能是 0(空间) / 1(指定组) / 2(私有)")

    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")

    doc_hash = hashlib.sha256(data).hexdigest()
    duplicated = (
        session.query(Doc)
        .filter(Doc.space_id == (ctx.space_id or 1), Doc.doc_hash == doc_hash)
        .first()
    )
    if duplicated is not None:
        raise HTTPException(409, f"同空间已存在内容相同的文档：doc_id={duplicated.id}")

    object_key = f"{uuid.uuid4().hex}{suffix}"
    dest = object_path(object_key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    doc = Doc(
        tenant_id=ctx.tenant_id,
        space_id=ctx.space_id or 1,
        title=title or file.filename or object_key,
        source_type=suffix.lstrip("."),
        object_key=object_key,
        doc_hash=doc_hash,
        visibility=visibility,
        acl_group=[int(x) for x in groups.split(",") if x.strip()],
        chunk_count=0,
        index_status=0,
        index_version=1,
        created_by=ctx.user_id,
    )
    session.add(doc)
    session.commit()

    enqueue_ingest(doc.id, background_tasks)
    return doc


@router.get("", response_model=list[DocOut])
def list_docs(ctx: RequestContext = Depends(current_ctx), session: Session = Depends(get_db)):
    query = session.query(Doc).filter(Doc.tenant_id == ctx.tenant_id)
    if ctx.space_id is not None:
        query = query.filter(Doc.space_id == ctx.space_id)
    return query.order_by(Doc.id.desc()).all()


@router.get("/{doc_id}/task", response_model=TaskOut | None)
def get_task(doc_id: int, ctx: RequestContext = Depends(current_ctx), session: Session = Depends(get_db)):
    _get_doc(session, doc_id, ctx)
    return session.query(IngestTask).filter(IngestTask.doc_id == doc_id).first()


@router.post("/{doc_id}/reindex", response_model=DocOut, status_code=202)
def reindex_doc(
    doc_id: int,
    background_tasks: BackgroundTasks,
    ctx: RequestContext = Depends(current_ctx),
    session: Session = Depends(get_db),
):
    doc = _get_doc(session, doc_id, ctx)
    doc.index_version += 1          # 新版本以 staging 写入，SWITCH 时原子切换
    doc.index_status = 0
    session.commit()

    task_repo.reset(doc.id)
    shutil.rmtree(work_dir(doc.id), ignore_errors=True)
    enqueue_ingest(doc.id, background_tasks)
    return doc


@router.delete("/{doc_id}")
def delete_doc(doc_id: int, ctx: RequestContext = Depends(current_ctx), session: Session = Depends(get_db)):
    doc = _get_doc(session, doc_id, ctx)
    purge_doc_index(doc.id)
    if doc.object_key:
        object_path(doc.object_key).unlink(missing_ok=True)
    session.query(IngestTask).filter(IngestTask.doc_id == doc.id).delete()
    session.delete(doc)
    session.commit()
    return {"deleted": doc_id}
