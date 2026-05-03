"""
Unit tests for backend services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── AI Service Tests ──────────────────────────────────────────────────────────

class TestAIService:
    """Tests for AIContractService."""

    def test_mock_mode_enabled_without_api_key(self):
        """Service should use mock mode when GROQ_API_KEY is not set."""
        with patch("backend.config.settings") as mock_settings:
            mock_settings.AI_MOCK_MODE = False
            mock_settings.GROQ_API_KEY = None
            from backend.services.ai_service import AIContractService
            svc = AIContractService()
            assert svc.mock_mode is True

    @pytest.mark.asyncio
    async def test_mock_contract_erc20(self):
        """Mock mode should return a valid ERC-20 contract."""
        with patch("backend.config.settings") as mock_settings:
            mock_settings.AI_MOCK_MODE = True
            mock_settings.GROQ_API_KEY = None
            from backend.services.ai_service import AIContractService
            svc = AIContractService()
            result = await svc.generate_contract(
                prompt="Create an ERC-20 token",
                contract_type="ERC20",
                contract_name="TestToken",
            )
            assert "source_code" in result
            assert "pragma solidity" in result["source_code"]
            assert result["model_used"] == "mock"

    @pytest.mark.asyncio
    async def test_mock_contract_erc721(self):
        """Mock mode should return a valid ERC-721 contract."""
        with patch("backend.config.settings") as mock_settings:
            mock_settings.AI_MOCK_MODE = True
            mock_settings.GROQ_API_KEY = None
            from backend.services.ai_service import AIContractService
            svc = AIContractService()
            result = await svc.generate_contract(
                prompt="Create an NFT collection",
                contract_type="ERC721",
                contract_name="TestNFT",
            )
            assert "ERC721" in result["source_code"]

    @pytest.mark.asyncio
    async def test_prompt_sanitization(self):
        """Dangerous prompts should generate warnings."""
        from backend.utils.security import sanitize_prompt
        _, warnings = sanitize_prompt("Create a contract with selfdestruct")
        assert len(warnings) > 0

    def test_solidity_output_extraction(self):
        """Should extract Solidity code from markdown-wrapped AI response."""
        from backend.utils.security import sanitize_solidity_output
        raw = "Here's your contract:\n```solidity\npragma solidity ^0.8.20;\ncontract Test {}\n```"
        result = sanitize_solidity_output(raw)
        assert "pragma solidity" in result
        assert "```" not in result


# ── Security Utilities Tests ──────────────────────────────────────────────────

class TestSecurityUtils:
    """Tests for JWT and password utilities."""

    def test_password_hashing_and_verification(self):
        from backend.utils.security import hash_password, verify_password
        plain = "SecurePassword123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_create_access_token(self):
        from backend.utils.security import create_access_token, decode_token
        token = create_access_token("user-id-123")
        payload = decode_token(token)
        assert payload["sub"] == "user-id-123"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        from backend.utils.security import create_refresh_token, decode_token, verify_token_type
        token = create_refresh_token("user-id-456")
        payload = decode_token(token)
        assert verify_token_type(payload, "refresh")
        assert not verify_token_type(payload, "access")

    def test_api_key_generation(self):
        from backend.utils.security import generate_api_key
        key = generate_api_key()
        assert key.startswith("scg_")
        assert len(key) > 20


# ── Audit Service Tests ───────────────────────────────────────────────────────

class TestAuditService:
    """Tests for the lightweight static analyzer."""

    @pytest.mark.asyncio
    async def test_detect_tx_origin(self):
        from backend.services.audit_service import AuditService
        svc = AuditService.__new__(AuditService)
        svc.slither_available = False

        source = """
        pragma solidity ^0.8.20;
        contract Test {
            function auth() public {
                require(tx.origin == owner, "Not authorized");
            }
        }
        """
        findings = svc._lightweight_analysis(source)
        titles = [f["title"] for f in findings]
        assert any("tx.origin" in t for t in titles)

    @pytest.mark.asyncio
    async def test_detect_selfdestruct(self):
        from backend.services.audit_service import AuditService
        svc = AuditService.__new__(AuditService)
        svc.slither_available = False

        source = "contract Test { function kill() external { selfdestruct(payable(msg.sender)); } }"
        findings = svc._lightweight_analysis(source)
        assert any("Self-Destruct" in f["title"] for f in findings)

    @pytest.mark.asyncio
    async def test_clean_contract_no_findings(self):
        from backend.services.audit_service import AuditService
        svc = AuditService.__new__(AuditService)
        svc.slither_available = False

        source = """
        pragma solidity ^0.8.20;
        import "@openzeppelin/contracts/access/Ownable.sol";
        import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
        contract CleanContract is Ownable, ReentrancyGuard {
            constructor(address o) Ownable(o) {}
        }
        """
        findings = svc._lightweight_analysis(source)
        assert len(findings) == 0

    def test_risk_score_calculation(self):
        from backend.services.audit_service import AuditService
        svc = AuditService.__new__(AuditService)
        svc.slither_available = False

        findings = [
            {"severity": "HIGH"}, {"severity": "MEDIUM"}, {"severity": "LOW"}
        ]
        score = svc._calculate_risk_score(findings)
        assert 0 <= score <= 100
        assert score > 0


# ── Compiler Service Tests ────────────────────────────────────────────────────

class TestCompilerService:
    """Tests for Solidity compilation."""

    def test_extract_contract_name(self):
        from backend.services.compiler_service import CompilerService
        svc = CompilerService.__new__(CompilerService)
        source = "pragma solidity ^0.8.20;\ncontract MyToken {\n}\ncontract AnotherContract {\n}"
        name = svc._extract_contract_name(source)
        assert name == "AnotherContract"

    def test_parse_solc_errors(self):
        from backend.services.compiler_service import CompilerService
        svc = CompilerService.__new__(CompilerService)
        error_output = "Error: undeclared identifier\nWarning: unused variable"
        errors, warnings = svc._parse_solc_errors(error_output)
        assert len(errors) == 1
        assert len(warnings) == 1
