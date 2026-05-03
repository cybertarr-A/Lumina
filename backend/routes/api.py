"""
Compile, audit, deploy, and WebSocket routes.
Production-grade: all heavy tasks dispatched to Celery workers.
Deploy flow includes wallet signature verification and mandatory audit gate.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.models import (
    AuditReport,
    AuditRequest,
    AuditResponse,
    AuditStatus,
    CompileRequest,
    CompileResponse,
    Contract,
    Deployment,
    DeploymentStatus,
    DeployRequest,
    DeployResponse,
    NetworkName,
    User,
)
from backend.routes.auth import get_current_user
from backend.services.blockchain_service import CHAIN_CONFIG
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ── Compile Router ────────────────────────────────────────────────────────────
compile_router = APIRouter(prefix="/compile", tags=["Compiler"])


@compile_router.post("/", status_code=202)
async def compile_contract(
    payload: CompileRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Enqueue a Solidity compilation job.
    Returns task_id for polling via GET /tasks/{task_id}.
    """
    from backend.tasks import compile_contract_task

    task = compile_contract_task.delay(
        source_code=payload.source_code,
        contract_id=None,
        optimizer=payload.optimizer,
        optimizer_runs=payload.optimizer_runs,
    )
    logger.info("compile_task_queued", task_id=task.id, user_id=str(current_user.id))
    return {"task_id": task.id, "status": "queued", "poll_url": f"/api/v1/tasks/{task.id}"}


@compile_router.post("/save/{contract_id}", status_code=202)
async def compile_and_save(
    contract_id: uuid.UUID,
    payload: CompileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue compilation and save ABI/bytecode to contract record on success."""
    from backend.tasks import compile_contract_task

    result_q = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    task = compile_contract_task.delay(
        source_code=payload.source_code,
        contract_id=str(contract_id),
        optimizer=payload.optimizer,
        optimizer_runs=payload.optimizer_runs,
    )
    logger.info("compile_save_task_queued", task_id=task.id, contract_id=str(contract_id))
    return {"task_id": task.id, "status": "queued", "poll_url": f"/api/v1/tasks/{task.id}"}


# ── Audit Router ──────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.post("/", response_model=AuditResponse, status_code=202)
async def run_audit(
    payload: AuditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enqueue a security audit job via Celery.
    Returns report ID immediately. Poll GET /tasks/{task_id} for progress.
    """
    from backend.tasks import run_audit_task

    result_q = await db.execute(
        select(Contract).where(Contract.id == payload.contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    report = AuditReport(contract_id=contract.id, status=AuditStatus.PENDING)
    db.add(report)
    await db.flush()
    await db.refresh(report)
    report_id = str(report.id)

    task = run_audit_task.delay(
        source_code=contract.source_code,
        contract_id=str(contract.id),
        report_id=report_id,
    )

    logger.info("audit_task_queued", task_id=task.id, report_id=report_id)
    # Attach task_id to report for frontend to poll
    report.summary = f"task_id:{task.id}"
    await db.flush()

    return report


@audit_router.get("/{report_id}", response_model=AuditResponse)
async def get_audit_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch an audit report by ID."""
    result_q = await db.execute(select(AuditReport).where(AuditReport.id == report_id))
    report = result_q.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Audit report not found")
    return report


# ── Deploy Router ─────────────────────────────────────────────────────────────
deploy_router = APIRouter(prefix="/deploy", tags=["Deployment"])

NETWORK_CHAIN_MAP = {
    NetworkName.ETH_MAINNET: 1,
    NetworkName.ETH_SEPOLIA: 11155111,
    NetworkName.POLYGON_MAINNET: 137,
    NetworkName.POLYGON_MUMBAI: 80001,
    NetworkName.BSC_MAINNET: 56,
    NetworkName.BSC_TESTNET: 97,
    NetworkName.LOCAL: 31337,
}

# Audit validity window — contract must have been audited within this period
AUDIT_VALIDITY_HOURS = 24


@deploy_router.post("/", response_model=DeployResponse, status_code=202)
async def initiate_deployment(
    payload: DeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initiate deployment with full security pipeline:
    1. Verify wallet signature (production only)
    2. Require recent audit (< 24h)
    3. Run deployment gate (blocks CRITICAL risk)
    4. Record deployment intent
    """
    from backend.pipeline.deploy_gate import deploy_gate, GateDecision
    from backend.config import settings

    # ── Step 1: Validate contract ownership ──────────────────────────────────
    result_q = await db.execute(
        select(Contract).where(Contract.id == payload.contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.is_compiled:
        raise HTTPException(status_code=400, detail="Contract must be compiled before deployment")

    # ── Step 2: Wallet signature verification ─────────────────────────────────
    if payload.signature and payload.signed_message:
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
            message = encode_defunct(text=payload.signed_message)
            recovered = Account.recover_message(message, signature=payload.signature)
            if recovered.lower() != payload.deployer_address.lower():
                raise HTTPException(
                    status_code=403,
                    detail=f"Signature verification failed: recovered {recovered} but expected {payload.deployer_address}",
                )
            logger.info("wallet_signature_verified", address=payload.deployer_address)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")
    elif settings.APP_ENV == "production":
        raise HTTPException(
            status_code=400,
            detail="Wallet signature required for deployment. Sign the deployment message in your wallet.",
        )

    # ── Step 3: Require recent audit ──────────────────────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(hours=AUDIT_VALIDITY_HOURS)
    audit_q = await db.execute(
        select(AuditReport)
        .where(
            AuditReport.contract_id == contract.id,
            AuditReport.status == AuditStatus.COMPLETED,
            AuditReport.completed_at >= cutoff,
        )
        .order_by(AuditReport.completed_at.desc())
        .limit(1)
    )
    latest_audit = audit_q.scalar_one_or_none()

    if not latest_audit:
        raise HTTPException(
            status_code=400,
            detail=(
                "Contract must be audited before deployment. "
                "Run POST /api/v1/audit/ first. "
                "A completed audit within the last 24 hours is required."
            ),
        )

    # ── Step 4: Deployment gate (risk score check) ────────────────────────────
    gate_result = deploy_gate.evaluate_from_db_report(
        risk_score=latest_audit.risk_score or 0.0,
        findings=latest_audit.findings or [],
    )

    if gate_result.decision == GateDecision.BLOCKED:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Deployment blocked by security gate",
                "reason": gate_result.reason,
                "risk_score": gate_result.risk_score,
                "risk_level": gate_result.risk_level,
                "can_override": False,
            },
        )

    # ── Step 5: Create deployment record ──────────────────────────────────────
    chain_id = NETWORK_CHAIN_MAP.get(payload.network, 31337)
    deployment = Deployment(
        contract_id=contract.id,
        user_id=current_user.id,
        network=payload.network,
        chain_id=chain_id,
        status=DeploymentStatus.PENDING,
        deployer_address=payload.deployer_address,
        constructor_args=payload.constructor_args,
    )
    db.add(deployment)
    await db.flush()
    await db.refresh(deployment)

    message = "Deployment initiated. Submit signed transaction via /deploy/{id}/confirm"
    if gate_result.decision == GateDecision.WARN:
        message = f"⚠️ {gate_result.reason} | {message}"

    logger.info(
        "deployment_initiated",
        deployment_id=str(deployment.id),
        risk_score=gate_result.risk_score,
        gate=gate_result.decision,
    )

    return DeployResponse(
        deployment_id=deployment.id,
        status=deployment.status,
        message=message,
    )


@deploy_router.post("/{deployment_id}/confirm")
async def confirm_deployment(
    deployment_id: uuid.UUID,
    tx_hash: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm a deployment with a MetaMask transaction hash.
    Enqueues a Celery polling task to track confirmation.
    """
    from backend.tasks import poll_deployment_task

    result_q = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = result_q.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment.status = DeploymentStatus.DEPLOYING
    deployment.transaction_hash = tx_hash
    await db.flush()

    task = poll_deployment_task.apply_async(
        args=[str(deployment_id), tx_hash, deployment.chain_id],
        countdown=5,  # Wait 5s before first poll
    )

    logger.info("deployment_poll_queued", task_id=task.id, tx_hash=tx_hash[:10])
    return {
        "message": "Polling for on-chain confirmation",
        "tx_hash": tx_hash,
        "task_id": task.id,
        "poll_url": f"/api/v1/tasks/{task.id}",
    }


@deploy_router.get("/{deployment_id}/status", response_model=DeployResponse)
async def get_deployment_status(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll deployment status from database."""
    result_q = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = result_q.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return DeployResponse(
        deployment_id=deployment.id,
        status=deployment.status,
        transaction_hash=deployment.transaction_hash,
        contract_address=deployment.contract_address,
        message=deployment.error_message or "OK",
    )


@deploy_router.get("/history/list")
async def deployment_history(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all deployments for the current user."""
    result_q = await db.execute(
        select(Deployment)
        .where(Deployment.user_id == current_user.id)
        .order_by(Deployment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    deployments = result_q.scalars().all()
    return [
        {
            "id": str(d.id),
            "contract_id": str(d.contract_id),
            "network": d.network.value,
            "status": d.status.value,
            "contract_address": d.contract_address,
            "transaction_hash": d.transaction_hash,
            "created_at": d.created_at.isoformat(),
        }
        for d in deployments
    ]


@deploy_router.get("/networks")
async def list_networks():
    """Return all supported blockchain networks."""
    from backend.services.blockchain_service import blockchain_service
    return blockchain_service.list_supported_networks()


# ── WebSocket Manager ─────────────────────────────────────────────────────────
ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.active:
            try:
                self.active[user_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, user_id: str, message: dict):
        dead = []
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


manager = ConnectionManager()


@ws_router.websocket("/notifications/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: str):
    """WebSocket endpoint for real-time deployment and audit notifications."""
    await manager.connect(user_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)
