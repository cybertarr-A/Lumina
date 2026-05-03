"""
Security Audit Service using Slither static analyzer.
Detects reentrancy, integer overflow, access control issues, and more.
"""
import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

SEVERITY_SCORE = {"high": 30, "medium": 15, "low": 5, "informational": 1, "optimization": 0}

SUGGESTION_MAP = {
    "reentrancy": "Apply ReentrancyGuard from OpenZeppelin or use checks-effects-interactions pattern.",
    "suicidal": "Remove selfdestruct or gate it behind a multi-sig timelock.",
    "unprotected-upgrade": "Add access control to upgrade functions using Ownable or AccessControl.",
    "controlled-delegatecall": "Validate delegate call targets against an allowlist.",
    "arbitrary-send-eth": "Validate recipient addresses and use pull-payment pattern.",
    "integer-overflow": "Use Solidity ^0.8.x built-in overflow checks or OpenZeppelin SafeMath.",
    "tx-origin": "Replace tx.origin with msg.sender for authentication.",
    "timestamp": "Avoid relying on block.timestamp for critical logic; use block.number instead.",
    "unchecked-transfer": "Check return values of ERC20 transfer/transferFrom using SafeERC20.",
}


class AuditService:
    """
    Runs Slither static analysis on Solidity source code.
    Falls back to a lightweight Python-based analyzer when Slither is unavailable.
    """

    def __init__(self):
        self.slither_available = self._check_slither()
        logger.info("audit_service_ready", slither=self.slither_available)

    def _check_slither(self) -> bool:
        """Check if Slither is installed."""
        return os.system("slither --version > /dev/null 2>&1") == 0

    async def run_audit(self, source_code: str, contract_id: str) -> Dict[str, Any]:
        """Run full security audit. Returns structured findings."""
        start = time.monotonic()
        findings = []

        if self.slither_available and settings.SLITHER_ENABLED:
            findings = await self._run_slither(source_code)
        else:
            findings = self._lightweight_analysis(source_code)

        risk_score = self._calculate_risk_score(findings)
        duration = round(time.monotonic() - start, 2)

        logger.info(
            "audit_completed",
            contract_id=contract_id,
            findings=len(findings),
            risk_score=risk_score,
            duration_s=duration,
        )

        return {
            "findings": findings,
            "risk_score": risk_score,
            "summary": self._generate_summary(findings, risk_score),
            "analysis_duration_seconds": duration,
        }

    async def _run_slither(self, source_code: str) -> List[Dict]:
        """Execute Slither as a subprocess and parse JSON output."""
        with tempfile.NamedTemporaryFile(suffix=".sol", mode="w", delete=False) as f:
            f.write(source_code)
            temp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "slither",
                temp_path,
                "--json",
                "-",
                "--solc-remaps",
                "@openzeppelin=node_modules/@openzeppelin",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=settings.AUDIT_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning("slither_timeout")
                return self._lightweight_analysis(source_code)

            if stdout:
                try:
                    data = json.loads(stdout.decode())
                    return self._parse_slither_output(data)
                except json.JSONDecodeError:
                    pass

            return self._lightweight_analysis(source_code)
        finally:
            os.unlink(temp_path)

    def _parse_slither_output(self, data: Dict) -> List[Dict]:
        """Convert Slither JSON output to our finding schema."""
        findings = []
        detectors = data.get("results", {}).get("detectors", [])
        for d in detectors:
            check = d.get("check", "unknown")
            findings.append({
                "id": str(uuid.uuid4()),
                "title": d.get("description", check)[:120],
                "description": d.get("description", ""),
                "severity": self._map_severity(d.get("impact", "low")),
                "location": self._extract_location(d),
                "suggestion": SUGGESTION_MAP.get(check, "Review and fix the identified issue."),
            })
        return findings

    def _lightweight_analysis(self, source_code: str) -> List[Dict]:
        """
        Python regex-based static analysis when Slither is unavailable.
        Detects common patterns without full AST parsing.
        """
        findings = []
        lines = source_code.split("\n")

        checks = [
            {
                "pattern": r"tx\.origin",
                "title": "tx.origin Authentication",
                "description": "Using tx.origin for authentication is dangerous as it can be exploited via phishing attacks.",
                "severity": "HIGH",
                "check": "tx-origin",
            },
            {
                "pattern": r"selfdestruct|suicide\(",
                "title": "Self-Destruct Usage",
                "description": "Contract contains selfdestruct which permanently removes the contract.",
                "severity": "HIGH",
                "check": "suicidal",
            },
            {
                "pattern": r"\.call\{value:",
                "title": "Low-Level Call with Value",
                "description": "Low-level .call with ETH transfer may be vulnerable to reentrancy.",
                "severity": "MEDIUM",
                "check": "reentrancy",
            },
            {
                "pattern": r"block\.timestamp",
                "title": "Timestamp Dependency",
                "description": "block.timestamp can be manipulated by miners within ~15 seconds.",
                "severity": "LOW",
                "check": "timestamp",
            },
            {
                "pattern": r"assembly\s*\{",
                "title": "Inline Assembly",
                "description": "Inline assembly bypasses Solidity safety checks.",
                "severity": "MEDIUM",
                "check": "assembly",
            },
            {
                "pattern": r"delegatecall",
                "title": "delegatecall Usage",
                "description": "Uncontrolled delegatecall can lead to proxy storage corruption.",
                "severity": "HIGH",
                "check": "controlled-delegatecall",
            },
        ]

        import re
        for check in checks:
            for i, line in enumerate(lines):
                if re.search(check["pattern"], line):
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "title": check["title"],
                        "description": check["description"],
                        "severity": check["severity"],
                        "location": f"Line {i + 1}: {line.strip()[:80]}",
                        "suggestion": SUGGESTION_MAP.get(check["check"], "Review and fix."),
                    })

        # Check for missing ReentrancyGuard with external calls
        has_external_call = bool(re.search(r"\.(call|send|transfer)\(", source_code))
        has_guard = "ReentrancyGuard" in source_code or "nonReentrant" in source_code
        if has_external_call and not has_guard:
            findings.append({
                "id": str(uuid.uuid4()),
                "title": "Missing Reentrancy Protection",
                "description": "Contract makes external calls without ReentrancyGuard.",
                "severity": "MEDIUM",
                "location": "Global",
                "suggestion": SUGGESTION_MAP["reentrancy"],
            })

        return findings

    def _map_severity(self, impact: str) -> str:
        mapping = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW", "informational": "INFO"}
        return mapping.get(impact.lower(), "INFO")

    def _extract_location(self, detector: Dict) -> str:
        elements = detector.get("elements", [])
        if elements:
            src = elements[0].get("source_mapping", {})
            return f"Line {src.get('lines', [0])[0]}" if src.get("lines") else "Unknown"
        return "Unknown"

    def _calculate_risk_score(self, findings: List[Dict]) -> float:
        """Calculate risk score 0-100 based on findings."""
        if not findings:
            return 0.0
        score = 0
        for f in findings:
            sev = f.get("severity", "INFO").lower()
            score += SEVERITY_SCORE.get(sev, 0)
        return min(100.0, round(score, 1))

    def _generate_summary(self, findings: List[Dict], risk_score: float) -> str:
        high = sum(1 for f in findings if f.get("severity") == "HIGH")
        medium = sum(1 for f in findings if f.get("severity") == "MEDIUM")
        low = sum(1 for f in findings if f.get("severity") == "LOW")

        if risk_score == 0:
            return "No security issues detected. Contract appears safe."
        level = "CRITICAL" if risk_score >= 70 else "HIGH" if risk_score >= 40 else "MEDIUM" if risk_score >= 20 else "LOW"
        return (
            f"Risk Level: {level} (score: {risk_score}/100). "
            f"Found {high} high, {medium} medium, {low} low severity issues. "
            f"{'Immediate remediation required.' if risk_score >= 40 else 'Review and address findings before deployment.'}"
        )


audit_service = AuditService()
