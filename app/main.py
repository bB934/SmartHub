"""应用入口：路由注册、CORS、启动期幂等初始化、前端静态托管。"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import chat, doc, search
from app.core.config import settings

logger = logging.getLogger("app")
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动期做幂等初始化；任一后端服务不可用只告警，不阻断启动。"""
    from app.db.es import ensure_index
    from app.db.milvus import ensure_collection
    from app.llm import cache

    for name, init in (
        ("Milvus 集合", ensure_collection),
        ("ES 索引", ensure_index),
        ("语义缓存集合", cache.ensure_collection),
    ):
        try:
            created = init()
            logger.info("%s %s", name, "已创建" if created else "已存在")
        except Exception as e:
            logger.warning("%s 初始化失败（服务仍可启动）：%s", name, e)
    yield


app = FastAPI(
    title="Enterprise RAG",
    version="1.0.0",
    lifespan=lifespan,
    # 默认 /docs 会和前端 SPA 的 /docs 路由冲突，统一挪到 /api/docs
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (doc.router, chat.router, search.router):
    app.include_router(r, prefix="/api/v1")

Instrumentator().instrument(app).expose(app)   # /metrics


@app.get("/health")
def health():
    return {"status": "ok"}


# 前端构建产物存在时由同一个进程托管，省去额外的 Nginx；开发期走 Vite dev server 代理
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # 兜底路由只接前端路由，未匹配的 /api 路径必须返回 404 而不是 HTML，
        # 否则前端拿到的“成功响应”会让错误排查变得很隐蔽
        if full_path.startswith(("api/", "metrics")):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(FRONTEND_DIST / "index.html")
