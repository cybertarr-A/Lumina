"""
Celery worker configuration for async background tasks.
Production-grade: separate queues for AI, audit, and deploy with
resource isolation, retry policies, and monitoring integration.
"""
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "lumina",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks"],
)

celery_app.conf.update(
    # ── Serialization ───────────────────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ── Timezone ────────────────────────────────────────────────────────────
    timezone="UTC",
    enable_utc=True,

    # ── Task behavior ───────────────────────────────────────────────────────
    task_track_started=True,
    task_acks_late=True,              # Acknowledge only after task completes
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes mid-task
    task_ignore_result=False,         # Store results for frontend polling

    # ── Worker resource limits ──────────────────────────────────────────────
    worker_prefetch_multiplier=1,     # One task at a time per worker process
    worker_max_tasks_per_child=50,    # Recycle worker after 50 tasks (memory leak prevention)
    worker_max_memory_per_child=512000,  # 512MB per worker process

    # ── Time limits ─────────────────────────────────────────────────────────
    task_time_limit=300,              # Hard kill after 5 min
    task_soft_time_limit=240,         # SIGTERM warning at 4 min

    # ── Result expiry ───────────────────────────────────────────────────────
    result_expires=3600,              # Keep task results for 1 hour

    # ── Queue routing ───────────────────────────────────────────────────────
    task_routes={
        "backend.tasks.generate_contract_task": {"queue": "ai"},
        "backend.tasks.compile_contract_task": {"queue": "ai"},
        "backend.tasks.run_audit_task": {"queue": "audit"},
        "backend.tasks.poll_deployment_task": {"queue": "deploy"},
    },

    # ── Queue priorities ────────────────────────────────────────────────────
    task_queue_max_priority=10,
    task_default_priority=5,

    # ── Beat schedule (periodic tasks) ─────────────────────────────────────
    beat_schedule={
        # Cleanup stale PENDING deployments older than 1 hour
        "cleanup-stale-deployments": {
            "task": "backend.tasks.poll_deployment_task",
            "schedule": 3600.0,
            "options": {"queue": "deploy"},
        },
    },

    # ── Broker connection resilience ────────────────────────────────────────
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,

    # ── Flower monitoring ───────────────────────────────────────────────────
    worker_send_task_events=True,
    task_send_sent_event=True,
)
