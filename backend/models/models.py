"""
SQLAlchemy ORM models and Pydantic schemas for all database entities.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Enum,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, EmailStr, Field, validator

from backend.database import Base


# ── Enumerations ───────────────────────────────────────────────────────────────

class ContractType(str, PyEnum):
    ERC20 = "ERC20"
    ERC721 = "ERC721"
    ERC1155 = "ERC1155"
    DAO = "DAO"
    STAKING = "STAKING"
    DEFI = "DEFI"
    CUSTOM = "CUSTOM"


class DeploymentStatus(str, PyEnum):
    PENDING = "PENDING"
    DEPLOYING = "DEPLOYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"


class AuditStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskLevel(str, PyEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class NetworkName(str, PyEnum):
    ETH_MAINNET = "ETH_MAINNET"
    ETH_SEPOLIA = "ETH_SEPOLIA"
    POLYGON_MAINNET = "POLYGON_MAINNET"
    POLYGON_MUMBAI = "POLYGON_MUMBAI"
    BSC_MAINNET = "BSC_MAINNET"
    BSC_TESTNET = "BSC_TESTNET"
    LOCAL = "LOCAL"


# ── SQLAlchemy ORM Models ──────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    contracts: Mapped[List["Contract"]] = relationship(
        "Contract", back_populates="owner", lazy="selectin"
    )
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="user", lazy="selectin"
    )


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_type: Mapped[ContractType] = mapped_column(
        Enum(ContractType), nullable=False, default=ContractType.CUSTOM
    )
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    abi: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    bytecode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compiler_version: Mapped[str] = mapped_column(String(20), default="0.8.20")
    is_compiled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    extra_metadata: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship("User", back_populates="contracts")
    versions: Mapped[List["ContractVersion"]] = relationship(
        "ContractVersion", back_populates="contract", lazy="selectin"
    )
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="contract", lazy="selectin"
    )
    audit_reports: Mapped[List["AuditReport"]] = relationship(
        "AuditReport", back_populates="contract", lazy="selectin"
    )


class ContractVersion(Base):
    __tablename__ = "contract_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_version"),
    )


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    network: Mapped[NetworkName] = mapped_column(Enum(NetworkName), nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False
    )
    contract_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    deployer_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    gas_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gas_price_gwei: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    constructor_args: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="deployments")
    user: Mapped["User"] = relationship("User", back_populates="deployments")


class AuditReport(Base):
    __tablename__ = "audit_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus), default=AuditStatus.PENDING, nullable=False
    )
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-100
    findings: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slither_output: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    mythril_output: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    analysis_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="audit_reports")


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ContractCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    contract_type: ContractType = ContractType.CUSTOM
    source_code: str = Field(..., min_length=10)
    tags: Optional[List[str]] = None


class ContractGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=2000)
    contract_type: Optional[ContractType] = None
    name: str = Field(..., min_length=1, max_length=255)
    template_params: Optional[Dict[str, Any]] = None


class ContractResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    contract_type: ContractType
    source_code: str
    abi: Optional[List]
    bytecode: Optional[str]
    is_compiled: bool
    ai_generated: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompileRequest(BaseModel):
    source_code: str = Field(..., min_length=10)
    contract_name: Optional[str] = None
    optimizer: bool = True
    optimizer_runs: int = Field(200, ge=1, le=10000)


class CompileResponse(BaseModel):
    success: bool
    abi: Optional[List] = None
    bytecode: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []
    gas_estimates: Optional[Dict[str, Any]] = None


class DeployRequest(BaseModel):
    contract_id: uuid.UUID
    network: NetworkName
    constructor_args: Optional[List[Any]] = None
    deployer_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    # Wallet signature for deployment authorization
    signed_message: Optional[str] = Field(None, description="The message that was signed by MetaMask")
    signature: Optional[str] = Field(None, description="Hex signature from eth_sign/personal_sign")


class DeployResponse(BaseModel):
    deployment_id: uuid.UUID
    status: DeploymentStatus
    transaction_hash: Optional[str] = None
    contract_address: Optional[str] = None
    message: str

    class Config:
        from_attributes = True


class AuditRequest(BaseModel):
    contract_id: uuid.UUID


class AuditFinding(BaseModel):
    id: str
    title: str
    description: str
    severity: RiskLevel
    location: Optional[str] = None
    suggestion: str


class AuditResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    status: AuditStatus
    risk_score: Optional[float]
    findings: Optional[List[AuditFinding]]
    summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        
