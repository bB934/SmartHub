
from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): pass

class Doc(Base):
    __tablename__ = "doc"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(index=True)
    space_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(16))
    object_key: Mapped[str | None] = mapped_column(String(255))
    doc_hash: Mapped[str] = mapped_column(String(64))
    visibility: Mapped[int] = mapped_column(default=0)      # 0空间 1指定组 2私有
    acl_group: Mapped[list[int]] = mapped_column(JSON, default=list)
    chunk_count: Mapped[int] = mapped_column(default=0)
    index_status: Mapped[int] = mapped_column(default=0)    # 0未生效 1生效 2废弃
    index_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[int | None]
    __table_args__ = (UniqueConstraint("space_id", "doc_hash", name="uk_space_hash"),)

class IngestTask(Base):
    __tablename__ = "ingest_task"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(index=True)
    stage: Mapped[str] = mapped_column(String(24))   # PARSE/SPLIT/EMBED/INDEX/SWITCH/DONE
    retry_count: Mapped[int] = mapped_column(default=0)
    error_msg: Mapped[str | None] = mapped_column(String(1000))