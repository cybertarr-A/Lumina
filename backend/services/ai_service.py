"""
AI Contract Generation Service using Groq API.
Converts natural language descriptions to Solidity smart contracts.
"""
import time
from typing import Optional

from groq import AsyncGroq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import settings
from backend.utils.logger import get_logger
from backend.utils.security import sanitize_prompt, sanitize_solidity_output

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert Solidity smart contract developer specializing in secure, gas-optimized contracts.

RULES:
1. Always include SPDX-License-Identifier comment
2. Always specify pragma solidity ^0.8.20
3. Use OpenZeppelin contracts where applicable
4. Follow checks-effects-interactions pattern
5. Add NatSpec documentation
6. Use custom errors instead of string reverts
7. Always emit events for state changes
8. NEVER use tx.origin for authentication
9. Output ONLY the Solidity code in a single ```solidity code block"""

CONTRACT_TYPE_HINTS = {
    "ERC20": "Use OpenZeppelin ERC20, ERC20Burnable, ERC20Pausable, Ownable.",
    "ERC721": "Use OpenZeppelin ERC721, ERC721URIStorage, Ownable with EIP-2981 royalties.",
    "ERC1155": "Use OpenZeppelin ERC1155, ERC1155Supply, Ownable.",
    "DAO": "Use OpenZeppelin Governor, GovernorSettings, GovernorCountingSimple, TimelockController.",
    "STAKING": "Implement staking with rewards, lock periods, and emergency withdrawal.",
    "DEFI": "Implement liquidity pool with AMM logic, fee collection, and slippage protection.",
}

ERC20_MOCK = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title {name}
/// @dev ERC-20 token — AI generated
contract {name} is ERC20, ERC20Burnable, ERC20Pausable, Ownable {{
    error ZeroAddress();
    event Minted(address indexed to, uint256 amount);

    constructor(address initialOwner, uint256 initialSupply)
        ERC20("{name}", "SCG") Ownable(initialOwner)
    {{
        if (initialOwner == address(0)) revert ZeroAddress();
        _mint(initialOwner, initialSupply * 10 ** decimals());
    }}

    function mint(address to, uint256 amount) external onlyOwner {{
        _mint(to, amount);
        emit Minted(to, amount);
    }}

    function pause() external onlyOwner {{ _pause(); }}
    function unpause() external onlyOwner {{ _unpause(); }}

    function _update(address from, address to, uint256 value)
        internal override(ERC20, ERC20Pausable)
    {{ super._update(from, to, value); }}
}}'''

ERC721_MOCK = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/// @title {name}
/// @dev ERC-721 NFT — AI generated
contract {name} is ERC721, ERC721URIStorage, Ownable {{
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIds;

    uint256 public maxSupply;
    uint256 public mintPrice;

    error MaxSupplyReached();
    error InsufficientPayment();

    event NFTMinted(address indexed to, uint256 tokenId, string uri);

    constructor(address initialOwner, uint256 _maxSupply, uint256 _mintPrice)
        ERC721("{name}", "NFT") Ownable(initialOwner)
    {{
        maxSupply = _maxSupply;
        mintPrice = _mintPrice;
    }}

    function safeMint(address to, string calldata uri) external payable {{
        if (_tokenIds.current() >= maxSupply) revert MaxSupplyReached();
        if (msg.value < mintPrice) revert InsufficientPayment();
        uint256 tokenId = _tokenIds.current();
        _tokenIds.increment();
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);
        emit NFTMinted(to, tokenId, uri);
    }}

    function withdraw() external onlyOwner {{
        (bool ok, ) = owner().call{{value: address(this).balance}}("");
        require(ok, "Transfer failed");
    }}

    function tokenURI(uint256 id) public view override(ERC721, ERC721URIStorage)
        returns (string memory) {{ return super.tokenURI(id); }}

    function supportsInterface(bytes4 id)
        public view override(ERC721, ERC721URIStorage) returns (bool)
    {{ return super.supportsInterface(id); }}
}}'''

DEFAULT_MOCK = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title {name}
/// @dev AI-generated contract (mock mode — configure GROQ_API_KEY for real AI)
contract {name} is Ownable, ReentrancyGuard {{
    event ValueUpdated(address indexed by, uint256 oldVal, uint256 newVal);

    uint256 private _value;

    constructor(address initialOwner) Ownable(initialOwner) {{}}

    function setValue(uint256 newValue) external onlyOwner nonReentrant {{
        uint256 old = _value;
        _value = newValue;
        emit ValueUpdated(msg.sender, old, newValue);
    }}

    function getValue() external view returns (uint256) {{ return _value; }}
}}'''


class AIContractService:
    """Groq-powered AI for generating Solidity contracts. Falls back to mock mode."""

    def __init__(self):
        self.mock_mode = settings.AI_MOCK_MODE or not settings.GROQ_API_KEY
        self.client: Optional[AsyncGroq] = None
        if not self.mock_mode:
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            logger.info("ai_service_ready", mode="groq")
        else:
            logger.warning("ai_service_ready", mode="mock")

    async def generate_contract(
        self,
        prompt: str,
        contract_type: Optional[str] = None,
        contract_name: str = "GeneratedContract",
        template_params: Optional[dict] = None,
    ) -> dict:
        start = time.monotonic()
        cleaned_prompt, warnings = sanitize_prompt(prompt)

        if self.mock_mode:
            code = self._mock_contract(contract_type, contract_name)
            return {
                "source_code": code,
                "warnings": warnings + ["Mock mode active — set GROQ_API_KEY for real AI"],
                "generation_time_ms": 50,
                "model_used": "mock",
            }

        user_msg = self._build_prompt(cleaned_prompt, contract_type, contract_name, template_params)
        raw = await self._call_groq(user_msg)
        code = sanitize_solidity_output(raw)
        elapsed = round((time.monotonic() - start) * 1000, 2)
        logger.info("contract_generated", ms=elapsed, type=contract_type)
        return {
            "source_code": code,
            "warnings": warnings,
            "generation_time_ms": elapsed,
            "model_used": settings.GROQ_MODEL,
        }

    def _build_prompt(self, prompt, contract_type, name, params):
        parts = [f"Generate a Solidity contract named '{name}'."]
        if contract_type and contract_type in CONTRACT_TYPE_HINTS:
            parts.append(f"Type: {contract_type}. {CONTRACT_TYPE_HINTS[contract_type]}")
        parts.append(f"Requirements: {prompt}")
        if params:
            parts.append(f"Parameters: {', '.join(f'{k}={v}' for k,v in params.items())}")
        return " ".join(parts)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        reraise=True,
    )
    async def _call_groq(self, message: str) -> str:
        resp = await self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=settings.GROQ_TEMPERATURE,
        )
        return resp.choices[0].message.content

    def _mock_contract(self, contract_type: Optional[str], name: str) -> str:
        if contract_type == "ERC20":
            return ERC20_MOCK.replace("{name}", name)
        elif contract_type == "ERC721":
            return ERC721_MOCK.replace("{name}", name)
        return DEFAULT_MOCK.replace("{name}", name)


ai_service = AIContractService()
