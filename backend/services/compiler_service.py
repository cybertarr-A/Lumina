"""
Solidity Compiler Service using py-solc-x.
Handles compilation, ABI extraction, bytecode generation, and gas estimation.
"""
import json
import re
from typing import Any, Dict, List, Optional

import solcx
from solcx import compile_source, install_solc

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CompilerService:
    """Manages Solidity compilation via py-solc-x."""

    def __init__(self):
        self._ensure_solc()

    def _ensure_solc(self) -> None:
        """Download and install the configured solc version if not present."""
        try:
            installed = [str(v) for v in solcx.get_installed_solc_versions()]
            target = settings.SOLC_VERSION
            if target not in installed:
                logger.info("installing_solc", version=target)
                install_solc(target)
            solcx.set_solc_version(target)
            logger.info("solc_ready", version=target)
        except Exception as e:
            logger.error("solc_setup_failed", error=str(e))

    def compile(
        self,
        source_code: str,
        contract_name: Optional[str] = None,
        optimizer: bool = True,
        optimizer_runs: int = 200,
    ) -> Dict[str, Any]:
        """
        Compile Solidity source code.
        Returns: {success, abi, bytecode, errors, warnings, gas_estimates}
        """
        result = {
            "success": False,
            "abi": None,
            "bytecode": None,
            "errors": [],
            "warnings": [],
            "gas_estimates": None,
        }

        # Extract contract name from source if not provided
        if not contract_name:
            contract_name = self._extract_contract_name(source_code)

        try:
            compiled = compile_source(
                source_code,
                output_values=["abi", "bin", "bin-runtime", "gas-estimates"],
                solc_version=settings.SOLC_VERSION,
                optimize=optimizer,
                optimize_runs=optimizer_runs,
            )

            # Find matching contract
            target_key = None
            for key in compiled:
                if contract_name and contract_name in key:
                    target_key = key
                    break
                if not contract_name:
                    target_key = key  # use first contract

            if not target_key:
                # Fall back to last contract in file
                target_key = list(compiled.keys())[-1]

            contract_data = compiled[target_key]
            result["success"] = True
            result["abi"] = contract_data.get("abi", [])
            result["bytecode"] = contract_data.get("bin", "")
            result["gas_estimates"] = contract_data.get("gas-estimates", {})

        except solcx.exceptions.SolcError as e:
            errors, warnings = self._parse_solc_errors(str(e))
            result["errors"] = errors
            result["warnings"] = warnings
            logger.warning("compilation_failed", errors=errors[:3])
        except Exception as e:
            result["errors"] = [f"Unexpected compiler error: {str(e)}"]
            logger.error("compiler_exception", error=str(e))

        return result

    def _extract_contract_name(self, source: str) -> Optional[str]:
        """Extract the last contract name from source via regex."""
        matches = re.findall(r"\bcontract\s+(\w+)", source)
        return matches[-1] if matches else None

    def _parse_solc_errors(self, error_output: str) -> tuple[List[str], List[str]]:
        """Separate errors from warnings in solc output."""
        errors, warnings = [], []
        for line in error_output.split("\n"):
            if "Error:" in line or "error:" in line.lower():
                errors.append(line.strip())
            elif "Warning:" in line or "warning:" in line.lower():
                warnings.append(line.strip())
        return errors, warnings

    def estimate_gas(self, abi: List, bytecode: str) -> Dict[str, Any]:
        """Provide a simple gas estimate summary from compiled output."""
        if not abi or not bytecode:
            return {}
        deployment_gas = len(bytes.fromhex(bytecode.replace("0x", ""))) * 200
        return {
            "deployment_estimate": deployment_gas,
            "bytecode_size_bytes": len(bytecode) // 2,
        }


compiler_service = CompilerService()
