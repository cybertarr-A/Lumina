"""
Celery worker configuration for async background tasks.
Handles AI generation, audit runs, and deployment polling.
"""
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "smartcontractgen",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.tasks.generate_contract_task": {"queue": "ai"},
        "backend.tasks.run_audit_task": {"queue": "audit"},
        "backend.tasks.poll_deployment_task": {"queue": "deploy"},
    },
    beat_schedule={},
)
