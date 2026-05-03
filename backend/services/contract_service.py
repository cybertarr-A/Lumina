"""
Solidity Contract Template Service.
Generates contracts from Jinja2 templates using OpenZeppelin base contracts.
"""
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "contracts" / "templates"


class ContractTemplateService:
    """Renders Solidity contracts from parameterized Jinja2 templates."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(disabled_extensions=("sol",)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        logger.info("template_service_ready", templates_dir=str(TEMPLATES_DIR))

    def render(self, template_name: str, params: Dict[str, Any]) -> str:
        """Render a contract template with given parameters."""
        template_file = f"{template_name}.sol"
        try:
            template = self.env.get_template(template_file)
            code = template.render(**params)
            logger.info("template_rendered", template=template_name)
            return code
        except Exception as e:
            logger.error("template_render_failed", template=template_name, error=str(e))
            raise

    def get_erc20(
        self,
        name: str,
        symbol: str,
        initial_supply: int = 1_000_000,
        mintable: bool = True,
        burnable: bool = True,
        pausable: bool = True,
        owner: Optional[str] = None,
    ) -> str:
        return self.render("ERC20", {
            "contract_name": name,
            "token_name": name,
            "token_symbol": symbol,
            "initial_supply": initial_supply,
            "mintable": mintable,
            "burnable": burnable,
            "pausable": pausable,
        })

    def get_erc721(
        self,
        name: str,
        symbol: str,
        max_supply: int = 10_000,
        mint_price_eth: float = 0.01,
        royalty_bps: int = 250,
    ) -> str:
        return self.render("ERC721", {
            "contract_name": name,
            "token_name": name,
            "token_symbol": symbol,
            "max_supply": max_supply,
            "mint_price_wei": int(mint_price_eth * 10**18),
            "royalty_bps": royalty_bps,
        })

    def get_erc1155(self, name: str, base_uri: str = "https://api.example.com/metadata/") -> str:
        return self.render("ERC1155", {
            "contract_name": name,
            "base_uri": base_uri,
        })

    def get_dao(self, name: str, token_address: str, voting_delay: int = 1, voting_period: int = 50400, quorum: int = 4) -> str:
        return self.render("DAO", {
            "contract_name": name,
            "token_address": token_address,
            "voting_delay": voting_delay,
            "voting_period": voting_period,
            "quorum_percentage": quorum,
        })

    def get_staking(
        self,
        name: str,
        staking_token: str,
        reward_token: str,
        reward_rate: int = 100,
        lock_period: int = 7 * 24 * 3600,
    ) -> str:
        return self.render("Staking", {
            "contract_name": name,
            "staking_token_address": staking_token,
            "reward_token_address": reward_token,
            "reward_rate": reward_rate,
            "lock_period": lock_period,
        })

    def list_templates(self) -> list:
        """List all available contract templates."""
        return [f.stem for f in TEMPLATES_DIR.glob("*.sol") if not f.name.startswith("_")]


template_service = ContractTemplateService()
