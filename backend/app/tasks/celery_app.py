"""
Celery application instance.
"""

from celery import Celery
from app.config import settings

celery_app = Celery(
    "nutrition_vision",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker (GPU safety)
    task_soft_time_limit=480,      # 8 min soft limit (depth model downloads ~100 MB on cold start)
    task_time_limit=600,           # 10 min hard limit
    result_expires=3600,           # Results expire after 1 hour
)
