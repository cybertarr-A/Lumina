"""
Deployment Gate — pre-deployment safety enforcement.

Evaluates a RiskReport and returns a GateDecision:
  APPROVED  — deploy freely
  WARN      — deploy with user-visible warning
  BLOCKED   — deployment rejected, reason provided

Thresholds match the RiskScoringEngine classification:
  SAFE / LOW     → APPROVED
  MEDIUM         → WARN
  HIGH           → WARN (with prominent alert, logged)
  CRITICAL (≥86) → BLOCKED
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.pipeline.risk_engine import RiskReport
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GateDecision(str, Enum):
    APPROVED = "APPROVED"
    WARN = "WARN"
    BLOCKED = "BLOCKED"


@dataclass
class GateResult:
    decision: GateDecision
    reason: str
    risk_score: float
    risk_level: str
    can_override: bool   # Whether user can bypass the warning (only for WARN)


class DeploymentGate:
    """
    Evaluates whether a contract is safe to deploy based on its risk report.
    CRITICAL-rated contracts are hard-blocked — no override possible.
    HIGH-rated contracts require explicit user acknowledgment (frontend enforced).
    """

    BLOCK_THRESHOLD = 86.0     # score ≥ 86 → always blocked
    WARN_HIGH_THRESHOLD = 66.0  # score ≥ 66 → warn, user must confirm
    WARN_MEDIUM_THRESHOLD = 41.0  # score ≥ 41 → warn, softer

    def evaluate(self, risk_report: RiskReport) -> GateResult:
        """
        Evaluate a RiskReport and return a GateResult.

        Args:
            risk_report: Output from RiskScoringEngine.calculate()

        Returns:
            GateResult with decision, reason, and override capability
        """
        score = risk_report.total_score
        level = risk_report.risk_level

        logger.info(
            "deployment_gate_evaluation",
            score=score,
            level=level,
            findings=risk_report.findings_breakdown,
        )

        if score >= self.BLOCK_THRESHOLD:
            reason = (
                f"Deployment BLOCKED: Contract risk score {score}/100 exceeds critical threshold (86). "
                f"Findings: {risk_report.findings_breakdown}. "
                f"Resolve all CRITICAL and HIGH vulnerabilities before deployment."
            )
            logger.warning("deployment_blocked", score=score, reason=reason)
            return GateResult(
                decision=GateDecision.BLOCKED,
                reason=reason,
                risk_score=score,
                risk_level=level,
                can_override=False,
            )

        if score >= self.WARN_HIGH_THRESHOLD:
            reason = (
                f"High-risk contract (score: {score}/100). "
                f"Found: {risk_report.findings_breakdown}. "
                f"Explicit acknowledgment required. Deploy only after reviewing all findings."
            )
            logger.warning("deployment_high_risk_warn", score=score)
            return GateResult(
                decision=GateDecision.WARN,
                reason=reason,
                risk_score=score,
                risk_level=level,
                can_override=True,
            )

        if score >= self.WARN_MEDIUM_THRESHOLD:
            reason = (
                f"Medium-risk contract (score: {score}/100). "
                f"Review findings before production deployment."
            )
            return GateResult(
                decision=GateDecision.WARN,
                reason=reason,
                risk_score=score,
                risk_level=level,
                can_override=True,
            )

        # SAFE or LOW
        return GateResult(
            decision=GateDecision.APPROVED,
            reason=f"Contract approved for deployment (score: {score}/100, level: {level})",
            risk_score=score,
            risk_level=level,
            can_override=False,
        )

    def evaluate_from_db_report(self, risk_score: float, findings: list) -> GateResult:
        """
        Evaluate gate from raw DB values (when full RiskReport not available).
        Used when checking a previously run audit report.
        """
        from backend.pipeline.risk_engine import risk_engine, RiskReport as RR
        level = risk_engine._classify(risk_score)
        mock_report = RR(
            total_score=risk_score,
            risk_level=level,
            summary="",
            security_score=0,
            complexity_score=0,
            external_call_score=0,
            privilege_score=0,
            deploy_blocked=risk_score >= 86,
            findings_breakdown={},
        )
        return self.evaluate(mock_report)


deploy_gate = DeploymentGate()
