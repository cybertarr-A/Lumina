# Lumina — Production-Grade Smart Contract Generator Platform

[![CI/CD](https://github.com/your-org/smartcontractgen/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/smartcontractgen/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

A full-stack Web3 platform for generating, compiling, auditing, and deploying Solidity smart contracts with AI assistance.

## Features

- 🤖 **AI Contract Generation** — Groq-powered (llama3-70b) NL → Solidity
- 📝 **Monaco Code Editor** — Solidity IntelliSense, syntax highlighting
- 🔒 **Security Audit** — Slither static analysis, risk scoring, fix suggestions
- 🚀 **Multi-Chain Deployment** — Ethereum, Polygon, BSC + testnets
- 👛 **Wallet Integration** — MetaMask + RainbowKit + WalletConnect
- 📦 **Contract Templates** — ERC-20, ERC-721, ERC-1155, DAO, Staking, DeFi
- 📊 **Observability** — Prometheus metrics, Grafana dashboards, Sentry
- 🐳 **Docker-first** — Full Docker Compose + Kubernetes manifests

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/smartcontractgen.git
cd smartcontractgen

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your GROQ_API_KEY and other settings
```

### 2. Start with Docker Compose

```bash
cd infra/docker
docker compose up -d

# Services:
# Frontend:   http://localhost:3000
# Backend:    http://localhost:8000
# API Docs:   http://localhost:8000/api/docs
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3001 (admin / admin123)
```

### 3. Local Development (without Docker)

**Backend:**
```bash
# Install PostgreSQL and Redis first
cd backend
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/smartcontract
export REDIS_URL=redis://localhost:6379/0
export SECRET_KEY=your-dev-secret-key
export AI_MOCK_MODE=true  # No Groq key needed for dev

# Run from the PROJECT ROOT (not from backend/)
cd "/run/media/cyber/359a6e28-9bc2-4e2c-9ca1-d2e8b64fde6b/Smart contract generator"
uvicorn backend.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install --legacy-peer-deps
cp .env.local.example .env.local  # or create manually
npm run dev  # http://localhost:3000
```

**Hardhat local blockchain:**
```bash
npm install
npx hardhat node  # Starts local EVM at http://localhost:8545
```

## Project Structure

```
├── backend/                   # FastAPI microservices
│   ├── main.py               # Application entry point
│   ├── config.py             # Pydantic settings
│   ├── database.py           # Async SQLAlchemy
│   ├── celery_worker.py      # Background task queue
│   ├── models/               # ORM models + Pydantic schemas
│   ├── routes/               # API routers (auth, contracts, compile, audit, deploy)
│   ├── services/             # Business logic (AI, compiler, audit, blockchain)
│   └── utils/                # Security, logging utilities
│
├── frontend/                  # Next.js 14 (App Router)
│   ├── app/                  # Pages (landing, dashboard, builder, deploy, audit)
│   ├── components/           # UI, Editor, Wallet, Layout components
│   └── lib/                  # API client, Wagmi config, Zustand stores
│
├── contracts/                 # Solidity templates (Jinja2)
│   └── templates/            # ERC20, ERC721, ERC1155, DAO, Staking, DeFi
│
├── scripts/                   # Hardhat deployment scripts
├── tests/                     # Unit, integration, contract, e2e tests
└── infra/
    ├── docker/               # Dockerfiles + docker-compose.yml
    ├── k8s/                  # Kubernetes manifests
    ├── monitoring/           # Prometheus + Grafana configs
    └── .github/workflows/    # CI/CD pipeline
```

## API Reference

Full OpenAPI docs available at `/api/docs` (development mode).

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login, get JWT |
| POST | `/api/v1/contracts/generate` | AI contract generation |
| POST | `/api/v1/compile/` | Compile Solidity |
| POST | `/api/v1/audit/` | Run security audit |
| POST | `/api/v1/deploy/` | Initiate deployment |
| GET | `/api/v1/deploy/networks` | List supported networks |
| WS | `/ws/notifications/{user_id}` | Real-time notifications |

## Supported Contract Types

| Type | Standard | Features |
|------|----------|----------|
| ERC-20 | OpenZeppelin | Mintable, Burnable, Pausable, MaxSupply |
| ERC-721 | OpenZeppelin | URI Storage, EIP-2981 Royalties, Pausable |
| ERC-1155 | OpenZeppelin | Batch Mint, Per-token URI, Pausable |
| DAO | OpenZeppelin Governor | TimelockController, Voting, Quorum |
| Staking | Custom | Reward Rate, Lock Period, Emergency Withdraw |
| DeFi | Custom | Via AI generation |

## Supported Networks

| Network | Chain ID | Type |
|---------|----------|------|
| Ethereum Mainnet | 1 | Production |
| Ethereum Sepolia | 11155111 | Testnet |
| Polygon Mainnet | 137 | Production |
| Polygon Mumbai | 80001 | Testnet |
| BSC Mainnet | 56 | Production |
| BSC Testnet | 97 | Testnet |
| Local (Hardhat) | 31337 | Development |

## Running Tests

```bash
# Backend unit + integration tests
cd backend && pytest tests/ -v --cov=backend

# Smart contract tests
npx hardhat test

# E2E tests (requires running app)
cd tests/e2e && npx playwright test
```

## Security

- JWT authentication with refresh token rotation
- Redis-based token blacklist for logout
- Rate limiting (100 req/min default)
- Input validation and Solidity output sanitization
- Slither static analysis integration
- Private keys never stored — client-side signing only

## License

MIT © 2025 Lumina
