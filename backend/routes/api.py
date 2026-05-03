"""
Compile, audit, deploy, and WebSocket routes.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
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
from backend.services.audit_service import audit_service
from backend.services.blockchain_service import blockchain_service, CHAIN_CONFIG
from backend.services.compiler_service import compiler_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Compile Router ────────────────────────────────────────────────────────────
compile_router = APIRouter(prefix="/compile", tags=["Compiler"])

@compile_router.post("/", response_model=CompileResponse)
async def compile_contract(
    payload: CompileRequest,
    current_user: User = Depends(get_current_user),
):
    """Compile Solidity source code and return ABI + bytecode."""
    result = compiler_service.compile(
        source_code=payload.source_code,
        optimizer=payload.optimizer,
        optimizer_runs=payload.optimizer_runs,
    )
    return CompileResponse(**result)


@compile_router.post("/save/{contract_id}")
async def compile_and_save(
    contract_id: uuid.UUID,
    payload: CompileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compile and save ABI/bytecode to the contract record."""
    result_q = await db.execute(
        select(Contract).where(Contract.id == contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    result = compiler_service.compile(payload.source_code, optimizer=payload.optimizer)
    if result["success"]:
        contract.abi = result["abi"]
        contract.bytecode = result["bytecode"]
        contract.is_compiled = True
        await db.flush()
        logger.info("contract_compiled_saved", contract_id=str(contract_id))

    return CompileResponse(**result)


# ── Audit Router ──────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/audit", tags=["Audit"])

@audit_router.post("/", response_model=AuditResponse, status_code=202)
async def run_audit(
    payload: AuditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a security audit for a contract (runs in background)."""
    result_q = await db.execute(
        select(Contract).where(Contract.id == payload.contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    report = AuditReport(
        contract_id=contract.id,
        status=AuditStatus.PENDING,
    )
    db.add(report)
    await db.flush()
    report_id = report.id

    background_tasks.add_task(
        _run_audit_task,
        report_id=report_id,
        source_code=contract.source_code,
        contract_id=str(contract.id),
    )

    await db.refresh(report)
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


async def _run_audit_task(report_id: uuid.UUID, source_code: str, contract_id: str):
    """Background task to run security analysis and update the report."""
    from backend.database import get_db_context
    async with get_db_context() as db:
        result_q = await db.execute(select(AuditReport).where(AuditReport.id == report_id))
        report = result_q.scalar_one_or_none()
        if not report:
            return

        report.status = AuditStatus.RUNNING
        await db.flush()

        try:
            audit_result = await audit_service.run_audit(source_code, contract_id)
            report.status = AuditStatus.COMPLETED
            report.findings = audit_result["findings"]
            report.risk_score = audit_result["risk_score"]
            report.summary = audit_result["summary"]
            report.analysis_duration_seconds = audit_result["analysis_duration_seconds"]
            report.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            report.status = AuditStatus.FAILED
            report.summary = f"Audit failed: {str(e)}"
            logger.error("audit_task_failed", report_id=str(report_id), error=str(e))

        await db.flush()


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


@deploy_router.post("/", response_model=DeployResponse, status_code=202)
async def initiate_deployment(
    payload: DeployRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Initiate a deployment. Returns deployment ID immediately.
    Actual on-chain deployment happens via frontend MetaMask signing.
    This records the deployment intent and waits for tx hash.
    """
    result_q = await db.execute(
        select(Contract).where(Contract.id == payload.contract_id, Contract.owner_id == current_user.id)
    )
    contract = result_q.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.is_compiled:
        raise HTTPException(status_code=400, detail="Contract must be compiled before deployment")

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

    logger.info("deployment_initiated", deployment_id=str(deployment.id))
    return DeployResponse(
        deployment_id=deployment.id,
        status=deployment.status,
        message="Deployment initiated. Submit signed transaction via /deploy/{id}/confirm",
    )


@deploy_router.post("/{deployment_id}/confirm")
async def confirm_deployment(
    deployment_id: uuid.UUID,
    tx_hash: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm a deployment by providing the transaction hash from MetaMask.
    Backend will then poll for receipt and update status.
    """
    result_q = await db.execute(
        select(Deployment).where(Deployment.id == deployment_id, Deployment.user_id == current_user.id)
    )
    deployment = result_q.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment.status = DeploymentStatus.DEPLOYING
    deployment.transaction_hash = tx_hash
    await db.flush()

    background_tasks.add_task(
        _poll_deployment, deployment_id=deployment_id, tx_hash=tx_hash, chain_id=deployment.chain_id
    )
    return {"message": "Polling for confirmation", "tx_hash": tx_hash}


@deploy_router.get("/{deployment_id}/status", response_model=DeployResponse)
async def get_deployment_status(
    deployment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll deployment status."""
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
        .offset(skip).limit(limit)
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
    return blockchain_service.list_supported_networks()


async def _poll_deployment(deployment_id: uuid.UUID, tx_hash: str, chain_id: int):
    """Background task: poll for transaction receipt and update deployment."""
    from backend.database import get_db_context
    async with get_db_context() as db:
        receipt = await blockchain_service.wait_for_receipt(chain_id, tx_hash)
        result_q = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result_q.scalar_one_or_none()
        if not deployment:
            return

        if receipt and receipt.get("status") == 1:
            deployment.status = DeploymentStatus.SUCCESS
            deployment.contract_address = receipt.get("contract_address")
            deployment.gas_used = receipt.get("gas_used")
            deployment.deployed_at = datetime.now(timezone.utc)
            logger.info("deployment_success", address=deployment.contract_address)
        else:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = "Transaction failed or not found"
            logger.warning("deployment_failed", deployment_id=str(deployment_id))
        await db.flush()


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
            self.active[user_id].remove(ws)

    async def broadcast(self, user_id: str, message: dict):
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@ws_router.websocket("/notifications/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: str):
    """WebSocket endpoint for real-time deployment and audit notifications."""
    await manager.connect(user_id, ws)
    try:
        while True:
            # Keep alive — client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)
