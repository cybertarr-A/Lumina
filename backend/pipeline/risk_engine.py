"""
Mathematical Risk Scoring Engine for Smart Contracts.

Risk Score = α·Security + β·Complexity + γ·ExternalCalls + δ·Privilege

Thresholds:
    0  – 20  : SAFE       (deploy allowed, green)
    21 – 40  : LOW        (deploy allowed, yellow)
    41 – 65  : MEDIUM     (deploy with warning, orange)
    66 – 85  : HIGH       (require explicit user acknowledgment, red)
    86 – 100 : CRITICAL   (deployment BLOCKED)
"""
import re
from dataclasses import dataclass, field
from typing import List


# ── Scoring Weights ────────────────────────────────────────────────────────────

FINDING_WEIGHTS = {
    "CRITICAL": 40.0,
    "HIGH":     25.0,
    "MEDIUM":   10.0,
    "LOW":       3.0,
    "INFO":      0.5,
}

ALPHA = 1.0   # Security findings weight
BETA  = 0.2   # Code complexity weight
GAMMA = 0.3   # External calls weight
DELTA = 0.5   # Privilege escalation weight

MAX_SCORE = 100.0


@dataclass
class RiskReport:
    total_score: float
    risk_level: str           # SAFE | LOW | MEDIUM | HIGH | CRITICAL
    summary: str
    security_score: float
    complexity_score: float
    external_call_score: float
    privilege_score: float
    deploy_blocked: bool
    findings_breakdown: dict = field(default_factory=dict)


class RiskScoringEngine:
    """
    Calculates a holistic risk score for a smart contract based on
    security findings, code complexity, external interactions, and
    privilege surface.
    """

    def calculate(self, findings: List[dict], source_code: str) -> RiskReport:
        """
        Compute full risk report.

        Args:
            findings: List of AuditFinding dicts with 'severity' keys
            source_code: Raw Solidity source code string

        Returns:
            RiskReport with all component scores and deployment decision
        """
        security = self._security_score(findings)
        complexity = self._complexity_score(source_code)
        external_calls = self._external_call_score(source_code)
        privilege = self._privilege_score(source_code)

        total = min(
            MAX_SCORE,
            ALPHA * security + BETA * complexity + GAMMA * external_calls + DELTA * privilege,
        )
        total = round(total, 2)

        risk_level = self._classify(total)
        deploy_blocked = total >= 86.0

        # Breakdown by severity
        breakdown = {}
        for finding in findings:
            sev = finding.get("severity", "INFO")
            breakdown[sev] = breakdown.get(sev, 0) + 1

        summary = self._build_summary(total, risk_level, breakdown, deploy_blocked)

        return RiskReport(
            total_score=total,
            risk_level=risk_level,
            summary=summary,
            security_score=round(security, 2),
            complexity_score=round(complexity, 2),
            external_call_score=round(external_calls, 2),
            privilege_score=round(privilege, 2),
            deploy_blocked=deploy_blocked,
            findings_breakdown=breakdown,
        )

    def _security_score(self, findings: List[dict]) -> float:
        """Weighted sum of all security findings."""
        score = 0.0
        for f in findings:
            sev = f.get("severity", "INFO").upper()
            score += FINDING_WEIGHTS.get(sev, 0.5)
        return min(score, 80.0)  # Cap security component at 80

    def _complexity_score(self, source_code: str) -> float:
        """
        Proxy for McCabe cyclomatic complexity.
        Counts control flow keywords as decision points.
        """
        keywords = ["if", "for", "while", "else", "require", "revert", "try", "catch"]
        score = 0.0
        for kw in keywords:
            count = len(re.findall(r"\b" + kw + r"\b", source_code))
            score += count * 0.5
        # Large bytecode penalty
        bytecode_proxy = len(source_code)
        if bytecode_proxy > 5000:
            score += (bytecode_proxy - 5000) / 1000
        return min(score, 40.0)

    def _external_call_score(self, source_code: str) -> float:
        """
        Score based on external call surface.
        Each .call/.send/.transfer and interface interaction adds risk.
        """
        patterns = [
            r"\.call\s*\(",           # low-level call
            r"\.send\s*\(",           # ETH send
            r"\.transfer\s*\(",       # ETH transfer
            r"\.delegatecall\s*\(",   # extra dangerous
            r"IERC\d+\s*\(",          # external token interactions
            r"IUniswap\w*\s*\(",      # DeFi protocol calls
        ]
        score = 0.0
        for pattern in patterns:
            matches = len(re.findall(pattern, source_code))
            weight = 8.0 if "delegatecall" in pattern else 5.0
            score += matches * weight
        return min(score, 50.0)

    def _privilege_score(self, source_code: str) -> float:
        """
        Score based on privilege escalation surface.
        Admin functions, ownership transfers, and upgrade patterns.
        """
        patterns = [
            r"\bonlyOwner\b",
            r"\bonlyRole\b",
            r"\bonlyAdmin\b",
            r"transferOwnership\s*\(",
            r"upgradeTo\s*\(",
            r"_authorizeUpgrade\s*\(",
            r"grantRole\s*\(",
            r"renounceOwnership\s*\(",
        ]
        score = 0.0
        for pattern in patterns:
            count = len(re.findall(pattern, source_code))
            score += count * 2.0
        return min(score, 30.0)

    def _classify(self, score: float) -> str:
        if score <= 20:
            return "SAFE"
        elif score <= 40:
            return "LOW"
        elif score <= 65:
            return "MEDIUM"
        elif score <= 85:
            return "HIGH"
        else:
            return "CRITICAL"

    def _build_summary(self, score: float, level: str, breakdown: dict, blocked: bool) -> str:
        crit = breakdown.get("CRITICAL", 0)
        high = breakdown.get("HIGH", 0)
        med = breakdown.get("MEDIUM", 0)
        low = breakdown.get("LOW", 0)

        if score == 0:
            return "No security issues detected. Contract appears safe for deployment."

        parts = [f"Risk Level: {level} (score: {score}/100)."]
        if crit:
            parts.append(f"{crit} critical,")
        if high:
            parts.append(f"{high} high,")
        if med:
            parts.append(f"{med} medium,")
        if low:
            parts.append(f"{low} low severity issue(s).")

        if blocked:
            parts.append("🚫 DEPLOYMENT BLOCKED — critical risk threshold exceeded.")
        elif level == "HIGH":
            parts.append("⚠️ High risk — explicit user acknowledgment required before deployment.")
        elif level == "MEDIUM":
            parts.append("Review and address findings before production deployment.")
        else:
            parts.append("Safe to deploy with standard precautions.")

        return " ".join(parts)


risk_engine = RiskScoringEngine()
