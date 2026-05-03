"""
Application configuration using Pydantic Settings.
All values loaded from environment variables with sensible defaults.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# Always resolve .env relative to the project root (two levels up from this file)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    APP_NAME: str = "Lumina"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── Security ───────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_OPENSSL_RAND_HEX_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ───────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smartcontract"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CACHE_TTL_SECONDS: int = 3600

    # ── CORS ───────────────────────────────────────────────────────
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://smartcontractgen.vercel.app",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, list]) -> List[str]:
        """Accept comma-separated string (Railway env vars) or JSON list."""
        if isinstance(v, str):
            if v.startswith("["):
                import json
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Rate Limiting ──────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # ── AI / Groq ──────────────────────────────────────────────────
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama3-70b-8192"
    GROQ_MAX_TOKENS: int = 4096
    GROQ_TEMPERATURE: float = 0.2
    AI_MOCK_MODE: bool = False  # Enable mock if no Groq key provided

    # ── Google OAuth ────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None

    # ── Blockchain RPC Endpoints ───────────────────────────────────
    ETH_MAINNET_RPC: str = "https://eth.llamarpc.com"
    ETH_SEPOLIA_RPC: str = "https://rpc.sepolia.org"
    POLYGON_MAINNET_RPC: str = "https://polygon-rpc.com"
    POLYGON_MUMBAI_RPC: str = "https://rpc-mumbai.maticvigil.com"
    BSC_MAINNET_RPC: str = "https://bsc-dataseed.binance.org"
    BSC_TESTNET_RPC: str = "https://data-seed-prebsc-1-s1.binance.org:8545"
    HARDHAT_RPC: str = "http://localhost:8545"

    # ── Solidity Compiler ──────────────────────────────────────────
    SOLC_VERSION: str = "0.8.20"
    SOLC_OPTIMIZE: bool = True
    SOLC_OPTIMIZE_RUNS: int = 200

    # ── Audit Tools ────────────────────────────────────────────────
    SLITHER_ENABLED: bool = True
    MYTHRIL_ENABLED: bool = False  # Heavy — enable in dedicated container
    AUDIT_TIMEOUT_SECONDS: int = 120

    # ── Supabase ───────────────────────────────────────────────────
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # ── Monitoring ─────────────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = True

    # ── File Storage ───────────────────────────────────────────────
    UPLOAD_DIR: str = "/tmp/smartcontract_uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def chain_rpc_map(self) -> dict:
        return {
            1: self.ETH_MAINNET_RPC,
            11155111: self.ETH_SEPOLIA_RPC,
            137: self.POLYGON_MAINNET_RPC,
            80001: self.POLYGON_MUMBAI_RPC,
            56: self.BSC_MAINNET_RPC,
            97: self.BSC_TESTNET_RPC,
            31337: self.HARDHAT_RPC,
        }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
