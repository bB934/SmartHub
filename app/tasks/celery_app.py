"""Celery 实例：生产环境用 worker 消费，本地默认走 BackgroundTasks（见 ingest_task.enqueue_ingest）。"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingest_task"],       # 延迟导入，避免与 task 模块循环引用
)
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1   # 长任务必须设 1，否则 worker 会被一个长任务占死

STAGES = ["PARSE", "SPLIT", "EMBED", "INDEX", "SWITCH", "DONE"]
