"""
Celery background tasks for all compute-heavy operations.
AI generation, compilation, security auditing, and deployment polling
all run here — keeping FastAPI event loop free for I/O.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from celery import states
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from backend.celery_worker import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── AI Contract Generation Task ────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="backend.tasks.generate_contract_task",
    queue="ai",
    max_retries=3,
    default_retry_delay=5,
    task_track_started=True,
    time_limit=120,
    soft_time_limit=100,
)
def generate_contract_task(
    self,
    prompt: str,
    contract_type: Optional[str],
    contract_name: str,
    contract_id: str,
    user_id: str,
    template_params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate a Solidity smart contract via Groq LLM.
    Runs pipeline: sanitize → generate → validate output → scan for critical patterns.
    Saves result back to the contracts table.
    """
    from backend.services.ai_service import ai_service
    from backend.utils.security import detect_critical_solidity_patterns
    from backend.pipeline.sanitizer import pipeline_sanitizer

    logger.info(f"generate_contract_task started: contract_id={contract_id}")
    self.update_state(state="STARTED", meta={"step": "generating", "progress": 10})

    try:
        # Run AI generation
        result = _run_async(
            ai_service.generate_contract(
                prompt=prompt,
                contract_type=contract_type,
                contract_name=contract_name,
                template_params=template_params,
            )
        )

        self.update_state(state="STARTED", meta={"step": "scanning", "progress": 75})

        # Scan output for critical patterns
        source_code = result["source_code"]
        violations = detect_critical_solidity_patterns(source_code)
        critical_violations = [v for v in violations if v["severity"] == "CRITICAL"]

        self.update_state(state="STARTED", meta={"step": "saving", "progress": 90})

        # Persist to database
        _run_async(_save_generated_contract(contract_id, source_code, result, violations))

        logger.info(f"generate_contract_task complete: contract_id={contract_id}, violations={len(violations)}")
        return {
            "success": True,
            "contract_id": contract_id,
            "source_code": source_code,
            "warnings": result.get("warnings", []),
            "critical_violations": critical_violations,
            "has_critical_issues": len(critical_violations) > 0,
            "generation_time_ms": result.get("generation_time_ms"),
            "model_used": result.get("model_used"),
        }

    except SoftTimeLimitExceeded:
        logger.error(f"generate_contract_task soft timeout: contract_id={contract_id}")
        raise self.retry(countdown=30, max_retries=1)
    except Exception as exc:
        logger.error(f"generate_contract_task failed: {exc}")
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)
        except MaxRetriesExceededError:
            return {"success": False, "error": str(exc), "contract_id": contract_id}


async def _save_generated_contract(contract_id: str, source_code: str, result: dict, violations: list):
    """Persist AI-generated contract back to DB."""
    from backend.database import get_db_context
    from backend.models.models import Contract
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id)))
        contract = q.scalar_one_or_none()
        if contract:
            contract.source_code = source_code
            contract.ai_generated = True
            contract.extra_metadata = {
                **(contract.extra_metadata or {}),
                "generation_warnings": result.get("warnings", []),
                "critical_violations": violations,
                "model_used": result.get("model_used"),
            }
            await db.flush()


# ── Compilation Task ───────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="backend.tasks.compile_contract_task",
    queue="ai",
    max_retries=2,
    default_retry_delay=3,
    task_track_started=True,
    time_limit=90,
    soft_time_limit=75,
)
def compile_contract_task(
    self,
    source_code: str,
    contract_id: Optional[str] = None,
    optimizer: bool = True,
    optimizer_runs: int = 200,
) -> Dict[str, Any]:
    """
    Compile Solidity source code via py-solc-x.
    Runs in Celery worker to keep FastAPI event loop free.
    Optionally saves ABI/bytecode to the contract record.
    """
    from backend.services.compiler_service import compiler_service

    logger.info(f"compile_contract_task started: contract_id={contract_id}")
    self.update_state(state="STARTED", meta={"step": "compiling", "progress": 20})

    try:
        result = compiler_service.compile(
            source_code=source_code,
            optimizer=optimizer,
            optimizer_runs=optimizer_runs,
        )

        # Persist if contract_id provided
        if contract_id and result.get("success"):
            self.update_state(state="STARTED", meta={"step": "saving", "progress": 85})
            _run_async(_save_compiled_contract(contract_id, result))

        logger.info(f"compile_contract_task complete: success={result['success']}")
        return {**result, "contract_id": contract_id}

    except Exception as exc:
        logger.error(f"compile_contract_task failed: {exc}")
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 3)
        except MaxRetriesExceededError:
            return {
                "success": False,
                "errors": [str(exc)],
                "warnings": [],
                "contract_id": contract_id,
            }


async def _save_compiled_contract(contract_id: str, result: dict):
    """Persist ABI and bytecode back to DB."""
    from backend.database import get_db_context
    from backend.models.models import Contract
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(Contract).where(Contract.id == uuid.UUID(contract_id)))
        contract = q.scalar_one_or_none()
        if contract:
            contract.abi = result.get("abi")
            contract.bytecode = result.get("bytecode")
            contract.is_compiled = True
            await db.flush()


# ── Security Audit Task ────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="backend.tasks.run_audit_task",
    queue="audit",
    max_retries=1,
    default_retry_delay=10,
    task_track_started=True,
    time_limit=180,
    soft_time_limit=150,
)
def run_audit_task(
    self,
    source_code: str,
    contract_id: str,
    report_id: str,
) -> Dict[str, Any]:
    """
    Run full security audit via Slither + lightweight analyzer.
    Updates the AuditReport record with findings and risk score.
    """
    from backend.services.audit_service import audit_service

    logger.info(f"run_audit_task started: report_id={report_id}")
    self.update_state(state="STARTED", meta={"step": "analyzing", "progress": 10})

    # Mark report as RUNNING
    _run_async(_update_audit_status(report_id, "RUNNING"))

    try:
        audit_result = _run_async(audit_service.run_audit(source_code, contract_id))

        self.update_state(state="STARTED", meta={"step": "scoring", "progress": 85})

        # Apply enhanced risk scoring from pipeline
        from backend.pipeline.risk_engine import risk_engine
        enhanced_score = risk_engine.calculate(
            findings=audit_result.get("findings", []),
            source_code=source_code,
        )

        _run_async(_save_audit_result(report_id, audit_result, enhanced_score))

        logger.info(f"run_audit_task complete: risk_score={enhanced_score.total_score}")
        return {
            "success": True,
            "report_id": report_id,
            "risk_score": enhanced_score.total_score,
            "risk_level": enhanced_score.risk_level,
            "findings_count": len(audit_result.get("findings", [])),
            "deploy_blocked": enhanced_score.total_score >= 86.0,
        }

    except Exception as exc:
        logger.error(f"run_audit_task failed: {exc}")
        _run_async(_update_audit_status(report_id, "FAILED", error=str(exc)))
        try:
            raise self.retry(exc=exc, countdown=15)
        except MaxRetriesExceededError:
            return {"success": False, "error": str(exc), "report_id": report_id}


async def _update_audit_status(report_id: str, status: str, error: Optional[str] = None):
    from backend.database import get_db_context
    from backend.models.models import AuditReport, AuditStatus
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(AuditReport).where(AuditReport.id == uuid.UUID(report_id)))
        report = q.scalar_one_or_none()
        if report:
            report.status = AuditStatus(status)
            if error:
                report.summary = f"Audit failed: {error}"
            await db.flush()


async def _save_audit_result(report_id: str, audit_result: dict, enhanced_score):
    from backend.database import get_db_context
    from backend.models.models import AuditReport, AuditStatus
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(AuditReport).where(AuditReport.id == uuid.UUID(report_id)))
        report = q.scalar_one_or_none()
        if report:
            report.status = AuditStatus.COMPLETED
            report.findings = audit_result.get("findings", [])
            report.risk_score = enhanced_score.total_score
            report.summary = enhanced_score.summary
            report.analysis_duration_seconds = audit_result.get("analysis_duration_seconds")
            report.completed_at = datetime.now(timezone.utc)
            await db.flush()


# ── Deployment Polling Task ────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="backend.tasks.poll_deployment_task",
    queue="deploy",
    max_retries=30,
    default_retry_delay=10,
    task_track_started=True,
    time_limit=360,
)
def poll_deployment_task(
    self,
    deployment_id: str,
    tx_hash: str,
    chain_id: int,
) -> Dict[str, Any]:
    """
    Poll blockchain for transaction receipt and update deployment record.
    Retries up to 30 times (5 min total) before marking as failed.
    """
    from backend.services.blockchain_service import blockchain_service

    logger.info(f"poll_deployment_task: deployment_id={deployment_id}, tx={tx_hash[:10]}...")
    self.update_state(state="STARTED", meta={"step": "polling", "tx_hash": tx_hash})

    try:
        receipt = _run_async(blockchain_service.get_transaction_receipt(chain_id, tx_hash))

        if receipt is None:
            # Not mined yet — retry
            raise self.retry(countdown=10)

        if receipt.get("status") == 1:
            _run_async(_save_deployment_success(deployment_id, receipt))
            logger.info(f"deployment_success: address={receipt.get('contract_address')}")
            return {
                "success": True,
                "deployment_id": deployment_id,
                "contract_address": receipt.get("contract_address"),
                "gas_used": receipt.get("gas_used"),
                "block_number": receipt.get("block_number"),
            }
        else:
            _run_async(_save_deployment_failed(deployment_id, "Transaction reverted on-chain"))
            return {"success": False, "deployment_id": deployment_id, "error": "Transaction reverted"}

    except Exception as exc:
        if "retry" in str(type(exc).__name__).lower():
            raise
        logger.error(f"poll_deployment_task failed: {exc}")
        try:
            raise self.retry(exc=exc, countdown=2 ** min(self.request.retries, 5) * 5)
        except MaxRetriesExceededError:
            _run_async(_save_deployment_failed(deployment_id, f"Polling timeout: {exc}"))
            return {"success": False, "deployment_id": deployment_id, "error": str(exc)}


async def _save_deployment_success(deployment_id: str, receipt: dict):
    from backend.database import get_db_context
    from backend.models.models import Deployment, DeploymentStatus
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(Deployment).where(Deployment.id == uuid.UUID(deployment_id)))
        dep = q.scalar_one_or_none()
        if dep:
            dep.status = DeploymentStatus.SUCCESS
            dep.contract_address = receipt.get("contract_address")
            dep.gas_used = receipt.get("gas_used")
            dep.deployed_at = datetime.now(timezone.utc)
            await db.flush()


async def _save_deployment_failed(deployment_id: str, reason: str):
    from backend.database import get_db_context
    from backend.models.models import Deployment, DeploymentStatus
    from sqlalchemy import select

    async with get_db_context() as db:
        q = await db.execute(select(Deployment).where(Deployment.id == uuid.UUID(deployment_id)))
        dep = q.scalar_one_or_none()
        if dep:
            dep.status = DeploymentStatus.FAILED
            dep.error_message = reason
            await db.flush()


# Avoid circular import — imported at runtime
from celery.exceptions import SoftTimeLimitExceeded
