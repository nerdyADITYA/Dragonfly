from uuid import UUID

from celery import Celery

from app.config import settings
from app.db import SessionLocal

celery = Celery("dragonfly", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_always_eager=settings.celery_eager, task_acks_late=True,
                   worker_prefetch_multiplier=1, task_track_started=True)


@celery.task(name="discovery.run")
def discovery_task(scan_id: str):
    from app.discovery import run_discovery

    with SessionLocal() as db:
        run_discovery(db, UUID(scan_id))


@celery.task(name="tests.run")
def test_run_task(run_id: str, test_case_ids: list[str]):
    from app.executor import run_tests

    with SessionLocal() as db:
        run_tests(db, UUID(run_id), [UUID(i) for i in test_case_ids])
