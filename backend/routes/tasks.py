"""
Task status polling endpoint.
Allows frontend to poll the state of any Celery background task.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from backend.celery_worker import celery_app
from backend.utils.logger import get_logger

router = APIRouter(prefix="/tasks", tags=["Tasks"])
logger = get_logger(__name__)


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str           # PENDING | STARTED | SUCCESS | FAILURE | RETRY | REVOKED
    step: Optional[str] = None     # e.g. "generating", "compiling", "scanning"
    progress: Optional[int] = None # 0-100
    result: Optional[Any] = None
    error: Optional[str] = None


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Poll the status of a background Celery task.

    Status values:
    - PENDING  — task queued, not yet picked up by a worker
    - STARTED  — task is actively running (includes step + progress)
    - SUCCESS  — task completed; result contains the output
    - FAILURE  — task failed; error contains the exception message
    - RETRY    — task encountered an error and is being retried
    - REVOKED  — task was manually cancelled
    """
    try:
        task = celery_app.AsyncResult(task_id)
        state = task.state

        if state == "PENDING":
            return TaskStatusResponse(task_id=task_id, status="PENDING", progress=0)

        if state == "STARTED":
            meta = task.info or {}
            return TaskStatusResponse(
                task_id=task_id,
                status="STARTED",
                step=meta.get("step"),
                progress=meta.get("progress", 0),
            )

        if state == "SUCCESS":
            return TaskStatusResponse(
                task_id=task_id,
                status="SUCCESS",
                progress=100,
                result=task.result,
            )

        if state == "FAILURE":
            error = str(task.result) if task.result else "Unknown error"
            return TaskStatusResponse(
                task_id=task_id,
                status="FAILURE",
                error=error,
            )

        # RETRY, REVOKED, or unknown
        return TaskStatusResponse(task_id=task_id, status=state)

    except Exception as e:
        logger.error("task_status_fetch_failed", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch task status: {str(e)}")


@router.delete("/{task_id}", status_code=204)
async def revoke_task(task_id: str) -> None:
    """Cancel a pending or running task."""
    try:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        logger.info("task_revoked", task_id=task_id)
    except Exception as e:
        logger.warning("task_revoke_failed", task_id=task_id, error=str(e))
