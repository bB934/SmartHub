"""建库任务：支持断点续跑与自动重试。

本机默认 use_celery=False，上传后由 FastAPI BackgroundTasks 直接跑，不需要额外起 worker；
生产环境把 USE_CELERY 设为 true，再 `celery -A app.tasks.celery_app worker -l info -c 4`。
"""

from fastapi import BackgroundTasks

from app.core.config import settings
from app.ingest.pipeline import run_stage
from app.tasks import repo as task_repo
from app.tasks.celery_app import STAGES, celery_app


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=2)
def ingest_doc(self, doc_id: int):
    task = task_repo.get_or_create(doc_id)
    start = STAGES.index(task.stage) if task.stage in STAGES else 0   # 断点续跑：从当前 stage 继续

    for stage in STAGES[start:]:
        try:
            run_stage(stage, doc_id)
            task_repo.set_stage(doc_id, stage)
        except Exception as e:
            task_repo.fail(doc_id, stage, str(e))
            raise                                    # 交给 autoretry；3 次后进死信


def enqueue_ingest(doc_id: int, background_tasks: BackgroundTasks | None = None) -> None:
    if settings.use_celery:
        ingest_doc.delay(doc_id)
    elif background_tasks is not None:
        background_tasks.add_task(ingest_doc.run, doc_id)
    else:
        ingest_doc.run(doc_id)
