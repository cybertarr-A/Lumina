"""
Contract management routes: generate, list, get, update, delete, versions.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.models import (
    Contract,
    ContractCreate,
    ContractGenerateRequest,
    ContractResponse,
    ContractType,
    ContractVersion,
    User,
)
from backend.routes.auth import get_current_user
from backend.services.ai_service import ai_service
from backend.services.contract_service import template_service
from backend.utils.logger import get_logger

router = APIRouter(prefix="/contracts", tags=["Contracts"])
logger = get_logger(__name__)


@router.post("/generate", response_model=ContractResponse, status_code=201)
async def generate_contract(
    payload: ContractGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a smart contract using AI or templates.
    If template_params provided with no AI prompt, uses template engine.
    Otherwise, uses Groq AI generation.
    """
    # Try template-first if contract_type is specified and prompt is simple
    source_code = None
    ai_generated = False
    warnings = []

    if payload.contract_type and payload.template_params:
        try:
            source_code = _render_template(payload.contract_type, payload.name, payload.template_params)
        except Exception as e:
            logger.warning("template_render_failed", error=str(e))

    if not source_code:
        # Fall back to AI generation
        result = await ai_service.generate_contract(
            prompt=payload.prompt,
            contract_type=payload.contract_type.value if payload.contract_type else None,
            contract_name=payload.name,
            template_params=payload.template_params,
        )
        source_code = result["source_code"]
        warnings = result["warnings"]
        ai_generated = True

    contract = Contract(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.prompt[:500] if payload.prompt else None,
        contract_type=payload.contract_type or ContractType.CUSTOM,
        source_code=source_code,
        ai_generated=ai_generated,
        ai_prompt=payload.prompt if ai_generated else None,
    )
    db.add(contract)
    await db.flush()

    # Create initial version
    version = ContractVersion(
        contract_id=contract.id,
        version_number=1,
        source_code=source_code,
        change_summary="Initial generation",
    )
    db.add(version)
    await db.flush()
    await db.refresh(contract)

    logger.info("contract_generated", contract_id=str(contract.id), ai=ai_generated)
    return contract


@router.post("/", response_model=ContractResponse, status_code=201)
async def create_contract(
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a contract from manually supplied source code."""
    contract = Contract(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        contract_type=payload.contract_type,
        source_code=payload.source_code,
        tags=payload.tags,
    )
    db.add(contract)
    await db.flush()

    version = ContractVersion(
        contract_id=contract.id,
        version_number=1,
        source_code=payload.source_code,
        change_summary="Manual creation",
    )
    db.add(version)
    await db.flush()
    await db.refresh(contract)
    return contract


@router.get("/", response_model=List[ContractResponse])
async def list_contracts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    contract_type: Optional[ContractType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all contracts owned by the current user."""
    query = select(Contract).where(
        Contract.owner_id == current_user.id,
        Contract.is_deleted == False,
    )
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
    query = query.offset(skip).limit(limit).order_by(Contract.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single contract by ID."""
    contract = await _get_owned_contract(db, contract_id, current_user.id)
    return contract


@router.put("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: uuid.UUID,
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a contract and create a new version."""
    contract = await _get_owned_contract(db, contract_id, current_user.id)

    # Determine next version number
    result = await db.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract.id)
        .order_by(ContractVersion.version_number.desc())
    )
    latest = result.scalars().first()
    next_version = (latest.version_number + 1) if latest else 1

    # Save new version
    version = ContractVersion(
        contract_id=contract.id,
        version_number=next_version,
        source_code=payload.source_code,
        change_summary="Manual edit",
    )
    db.add(version)

    # Update contract
    contract.name = payload.name
    contract.description = payload.description
    contract.source_code = payload.source_code
    contract.tags = payload.tags
    contract.is_compiled = False  # Reset on edit
    contract.abi = None
    contract.bytecode = None

    await db.flush()
    await db.refresh(contract)
    logger.info("contract_updated", contract_id=str(contract.id), version=next_version)
    return contract


@router.delete("/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a contract."""
    contract = await _get_owned_contract(db, contract_id, current_user.id)
    contract.is_deleted = True
    await db.flush()
    logger.info("contract_deleted", contract_id=str(contract_id))


@router.get("/{contract_id}/versions")
async def list_versions(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all saved versions of a contract."""
    await _get_owned_contract(db, contract_id, current_user.id)
    result = await db.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(ContractVersion.version_number.asc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "change_summary": v.change_summary,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


@router.get("/templates/list")
async def list_templates(current_user: User = Depends(get_current_user)):
    """List available contract templates."""
    return {
        "templates": template_service.list_templates(),
        "types": [t.value for t in ContractType],
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_owned_contract(
    db: AsyncSession, contract_id: uuid.UUID, owner_id: uuid.UUID
) -> Contract:
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.owner_id == owner_id,
            Contract.is_deleted == False,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


def _render_template(contract_type: ContractType, name: str, params: dict) -> str:
    """Render a contract from the template engine."""
    if contract_type == ContractType.ERC20:
        return template_service.get_erc20(name=name, **params)
    elif contract_type == ContractType.ERC721:
        return template_service.get_erc721(name=name, **params)
    elif contract_type == ContractType.ERC1155:
        return template_service.get_erc1155(name=name, **params)
    elif contract_type == ContractType.DAO:
        return template_service.get_dao(name=name, **params)
    elif contract_type == ContractType.STAKING:
        return template_service.get_staking(name=name, **params)
    raise ValueError(f"No template for type: {contract_type}")
