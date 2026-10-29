"""SQLAlchemy engine / Session 工厂。engine 是懒连接，import 期不会真正连库。"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.mysql_dsn, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：请求结束自动关闭 session。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
