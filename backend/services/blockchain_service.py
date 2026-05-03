"""
Blockchain service for multi-chain contract deployment and interaction.
Uses Web3.py with support for Ethereum, Polygon, and BSC.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from web3 import AsyncWeb3, Web3
from web3.middleware import geth_poa_middleware

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

CHAIN_CONFIG = {
    1:       {"name": "Ethereum Mainnet",  "rpc": settings.ETH_MAINNET_RPC,      "explorer": "https://etherscan.io"},
    11155111:{"name": "Ethereum Sepolia",  "rpc": settings.ETH_SEPOLIA_RPC,      "explorer": "https://sepolia.etherscan.io"},
    137:     {"name": "Polygon Mainnet",   "rpc": settings.POLYGON_MAINNET_RPC,  "explorer": "https://polygonscan.com"},
    80001:   {"name": "Polygon Mumbai",    "rpc": settings.POLYGON_MUMBAI_RPC,   "explorer": "https://mumbai.polygonscan.com"},
    56:      {"name": "BSC Mainnet",       "rpc": settings.BSC_MAINNET_RPC,      "explorer": "https://bscscan.com"},
    97:      {"name": "BSC Testnet",       "rpc": settings.BSC_TESTNET_RPC,      "explorer": "https://testnet.bscscan.com"},
    31337:   {"name": "Hardhat Local",     "rpc": settings.HARDHAT_RPC,          "explorer": ""},
}

POA_CHAINS = {137, 80001, 56, 97}


class BlockchainService:
    """
    Multi-chain Web3 service for contract deployment and interaction.
    NOTE: Private key signing is done client-side (MetaMask/hardware wallet).
    This service only handles deployment via pre-signed transactions.
    """

    def __init__(self):
        self._connections: Dict[int, AsyncWeb3] = {}

    def get_connection(self, chain_id: int) -> AsyncWeb3:
        """Get or create a Web3 connection for the given chain."""
        if chain_id not in self._connections:
            cfg = CHAIN_CONFIG.get(chain_id)
            if not cfg:
                raise ValueError(f"Unsupported chain ID: {chain_id}")

            w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(cfg["rpc"]))
            if chain_id in POA_CHAINS:
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            self._connections[chain_id] = w3
            logger.info("web3_connected", chain=cfg["name"])

        return self._connections[chain_id]

    async def is_connected(self, chain_id: int) -> bool:
        """Check if the RPC endpoint is reachable."""
        try:
            w3 = self.get_connection(chain_id)
            return await w3.is_connected()
        except Exception:
            return False

    async def get_gas_price(self, chain_id: int) -> Dict[str, int]:
        """Get current gas price and EIP-1559 fees for a chain."""
        w3 = self.get_connection(chain_id)
        try:
            gas_price = await w3.eth.gas_price
            block = await w3.eth.get_block("latest")
            base_fee = block.get("baseFeePerGas", gas_price)
            return {
                "gas_price_wei": gas_price,
                "gas_price_gwei": round(Web3.from_wei(gas_price, "gwei"), 2),
                "base_fee_wei": base_fee,
                "max_priority_fee_gwei": 2,  # Standard tip
            }
        except Exception as e:
            logger.warning("gas_price_fetch_failed", chain_id=chain_id, error=str(e))
            return {"gas_price_gwei": 20, "gas_price_wei": 20_000_000_000}

    async def estimate_deployment_gas(
        self, chain_id: int, abi: List, bytecode: str, constructor_args: Optional[List] = None
    ) -> int:
        """Estimate gas required to deploy a contract."""
        w3 = self.get_connection(chain_id)
        try:
            contract = w3.eth.contract(abi=abi, bytecode=bytecode)
            if constructor_args:
                gas = await contract.constructor(*constructor_args).estimate_gas()
            else:
                gas = await contract.constructor().estimate_gas()
            return gas
        except Exception as e:
            logger.warning("gas_estimate_failed", error=str(e))
            # Fallback: rough estimate from bytecode size
            return len(bytes.fromhex(bytecode.replace("0x", ""))) * 68 + 21000

    async def get_transaction_receipt(self, chain_id: int, tx_hash: str) -> Optional[Dict]:
        """Poll for a transaction receipt."""
        w3 = self.get_connection(chain_id)
        try:
            receipt = await w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                return {
                    "status": receipt.status,
                    "contract_address": receipt.get("contractAddress"),
                    "gas_used": receipt.gasUsed,
                    "block_number": receipt.blockNumber,
                    "transaction_hash": receipt.transactionHash.hex(),
                }
        except Exception as e:
            logger.warning("receipt_fetch_failed", tx_hash=tx_hash, error=str(e))
        return None

    async def wait_for_receipt(
        self, chain_id: int, tx_hash: str, timeout: int = 300, poll_interval: int = 3
    ) -> Optional[Dict]:
        """Wait for transaction to be mined, polling at intervals."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            receipt = await self.get_transaction_receipt(chain_id, tx_hash)
            if receipt:
                return receipt
            await asyncio.sleep(poll_interval)
        logger.warning("receipt_timeout", tx_hash=tx_hash)
        return None

    async def get_contract_instance(self, chain_id: int, address: str, abi: List) -> Any:
        """Get a contract instance for reading/writing."""
        w3 = self.get_connection(chain_id)
        checksum_addr = Web3.to_checksum_address(address)
        return w3.eth.contract(address=checksum_addr, abi=abi)

    def get_explorer_url(self, chain_id: int, tx_or_address: str, tx: bool = True) -> str:
        """Build a block explorer URL for a tx hash or contract address."""
        cfg = CHAIN_CONFIG.get(chain_id, {})
        base = cfg.get("explorer", "")
        if not base:
            return ""
        path = "tx" if tx else "address"
        return f"{base}/{path}/{tx_or_address}"

    def list_supported_networks(self) -> List[Dict]:
        """Return all supported networks with metadata."""
        return [
            {
                "chain_id": chain_id,
                "name": cfg["name"],
                "explorer": cfg["explorer"],
                "rpc": cfg["rpc"],
            }
            for chain_id, cfg in CHAIN_CONFIG.items()
        ]


blockchain_service = BlockchainService()
