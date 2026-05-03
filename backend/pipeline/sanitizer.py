"""
Contract Security Pipeline — Sanitizer Layer.
Multi-stage sanitization for both AI prompts and generated Solidity output.
"""
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class SanitizeResult:
    is_safe: bool
    sanitized_text: str
    violations: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── Pattern Definitions ────────────────────────────────────────────────────────

JAILBREAK_PATTERNS = [
    r"ignore\s+(?:previous|above|all)\s+instructions?",
    r"disregard\s+(?:all|previous|your)\s+instructions?",
    r"forget\s+(?:all|previous|your)\s+instructions?",
    r"new\s+instructions?:",
    r"(?:you\s+are\s+now|act\s+as|pretend\s+(?:you\s+are|to\s+be))\s+",
    r"(?:jailbreak|DAN\b|override\s+(?:safety|restrictions?|constraints?))",
    r"(?:bypass|circumvent)\s+(?:the\s+)?(?:safety|filter|restriction)",
    r"<\|im_(?:start|end)\|>",
    r"```\s*system",
    r"SYSTEM\s+PROMPT",
]

# Solidity-critical patterns — always flag these in generated output
CRITICAL_SOLIDITY_PATTERNS = [
    {
        "pattern": r"\bselfdestruct\b",
        "severity": "CRITICAL",
        "title": "Self-Destruct",
        "description": "selfdestruct permanently destroys the contract and sends ETH to target",
        "suggestion": "Remove selfdestruct or gate behind multi-sig timelock",
    },
    {
        "pattern": r"\bsuicide\s*\(",
        "severity": "CRITICAL",
        "title": "Deprecated selfdestruct alias",
        "description": "suicide() is a deprecated alias for selfdestruct",
        "suggestion": "Remove this call entirely",
    },
    {
        "pattern": r"\bdelegatecall\b",
        "severity": "HIGH",
        "title": "Delegatecall",
        "description": "Uncontrolled delegatecall can overwrite storage via malicious contract",
        "suggestion": "Validate delegatecall targets against a strict allowlist",
    },
    {
        "pattern": r"\btx\.origin\b",
        "severity": "HIGH",
        "title": "tx.origin Authentication",
        "description": "tx.origin can be spoofed via phishing contracts to impersonate users",
        "suggestion": "Replace tx.origin with msg.sender for all authentication checks",
    },
    {
        "pattern": r"\bassembly\s*\{",
        "severity": "MEDIUM",
        "title": "Inline Assembly",
        "description": "Inline assembly bypasses Solidity type safety and overflow checks",
        "suggestion": "Replace with high-level Solidity or use audited assembly libraries",
    },
]

# Dangerous patterns in prompts (code injection attempts)
PROMPT_CODE_INJECTION = [
    r"__import__\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"os\.system\s*\(",
    r"subprocess\.",
    r"import\s+os\b",
    r"import\s+sys\b",
    r"(?:wget|curl)\s+https?://",
    r"chmod\s+\d{3}",
    r"\brm\s+-rf\b",
]


class ContractPipelineSanitizer:
    """
    Multi-stage sanitizer for the AI contract generation pipeline.

    Stage 1 (prompt_sanitize): blocks jailbreaks and code injection before hitting LLM
    Stage 2 (output_sanitize): validates and cleans LLM-generated Solidity
    Stage 3 (detect_critical): scans for must-flag security patterns
    """

    def sanitize_prompt(self, prompt: str) -> SanitizeResult:
        """
        Sanitize user prompt before sending to LLM.
        Returns SanitizeResult with is_safe=False if injection detected.
        """
        violations = []
        warnings = []
        cleaned = prompt.strip()

        # Length limit
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000]
            warnings.append("Prompt truncated to 2000 characters")

        # Jailbreak detection
        for pattern in JAILBREAK_PATTERNS:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                violations.append({
                    "type": "jailbreak",
                    "pattern": pattern,
                    "matched": match.group(0),
                    "severity": "CRITICAL",
                })
                cleaned = re.sub(pattern, "[REMOVED]", cleaned, flags=re.IGNORECASE)

        # Code injection in prompt
        for pattern in PROMPT_CODE_INJECTION:
            if re.search(pattern, cleaned, re.IGNORECASE):
                violations.append({
                    "type": "code_injection",
                    "pattern": pattern,
                    "severity": "HIGH",
                })
                cleaned = re.sub(pattern, "[BLOCKED]", cleaned, flags=re.IGNORECASE)

        is_safe = not any(v["severity"] == "CRITICAL" for v in violations)
        return SanitizeResult(
            is_safe=is_safe,
            sanitized_text=cleaned,
            violations=violations,
            warnings=warnings,
        )

    def sanitize_output(self, source_code: str) -> SanitizeResult:
        """
        Validate and clean LLM-generated Solidity output.
        Ensures minimum structure (SPDX, pragma, contract keyword).
        """
        warnings = []
        cleaned = source_code.strip()

        # Must contain SPDX identifier
        if "SPDX-License-Identifier" not in cleaned:
            warnings.append("Missing SPDX-License-Identifier — adding MIT default")
            cleaned = "// SPDX-License-Identifier: MIT\n" + cleaned

        # Must contain pragma solidity
        if "pragma solidity" not in cleaned:
            warnings.append("Missing pragma solidity — output may be invalid")

        # Must contain at least one contract/interface/library
        if not re.search(r"\b(?:contract|interface|library|abstract\s+contract)\b", cleaned):
            return SanitizeResult(
                is_safe=False,
                sanitized_text=cleaned,
                violations=[{"type": "invalid_output", "severity": "CRITICAL",
                             "message": "LLM output does not contain valid Solidity contract"}],
            )

        return SanitizeResult(is_safe=True, sanitized_text=cleaned, warnings=warnings)

    def detect_critical_patterns(self, source_code: str) -> List[dict]:
        """
        Scan Solidity source for critical security patterns.
        Returns list of findings — does NOT modify source code.
        """
        findings = []
        lines = source_code.split("\n")

        for check in CRITICAL_SOLIDITY_PATTERNS:
            for i, line in enumerate(lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue
                if re.search(check["pattern"], line, re.IGNORECASE):
                    findings.append({
                        **check,
                        "line": i,
                        "code_snippet": line.strip()[:120],
                    })

        return findings


pipeline_sanitizer = ContractPipelineSanitizer()
