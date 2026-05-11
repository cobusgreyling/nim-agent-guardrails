"""Guardrail definitions — composable checks that wrap NIM API calls."""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class GuardrailResult:
    """Outcome of a single guardrail check."""
    passed: bool
    guardrail_name: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Guardrail(ABC):
    """Base guardrail — subclass and implement ``check``."""

    name: str = "base"

    @abstractmethod
    def check(self, *, input_text: str | None = None,
              output_text: str | None = None,
              tool_calls: list[dict] | None = None,
              context: dict[str, Any] | None = None) -> GuardrailResult:
        ...

    def _ok(self, msg: str = "", **meta: Any) -> GuardrailResult:
        return GuardrailResult(passed=True, guardrail_name=self.name,
                               message=msg, metadata=meta)

    def _fail(self, msg: str, **meta: Any) -> GuardrailResult:
        return GuardrailResult(passed=False, guardrail_name=self.name,
                               message=msg, metadata=meta)


# ---------------------------------------------------------------------------
# Guardrail chain
# ---------------------------------------------------------------------------

class GuardrailChain:
    """Run multiple guardrails in sequence; short-circuit on first failure."""

    def __init__(self, guardrails: list[Guardrail] | None = None):
        self.guardrails: list[Guardrail] = guardrails or []

    def add(self, guardrail: Guardrail) -> "GuardrailChain":
        self.guardrails.append(guardrail)
        return self

    def run(self, **kwargs: Any) -> list[GuardrailResult]:
        results: list[GuardrailResult] = []
        for g in self.guardrails:
            t0 = time.perf_counter()
            result = g.check(**kwargs)
            result.latency_ms = (time.perf_counter() - t0) * 1000
            results.append(result)
            if not result.passed:
                break  # short-circuit
        return results

    def all_passed(self, results: list[GuardrailResult]) -> bool:
        return all(r.passed for r in results)


# ---------------------------------------------------------------------------
# Built-in guardrails
# ---------------------------------------------------------------------------

class InputLengthGuardrail(Guardrail):
    """Reject inputs that exceed a character or token-estimate limit."""

    name = "input_length"

    def __init__(self, max_chars: int = 4000, max_tokens_estimate: int = 1500):
        self.max_chars = max_chars
        self.max_tokens_estimate = max_tokens_estimate

    def check(self, *, input_text: str | None = None, **_: Any) -> GuardrailResult:
        if input_text is None:
            return self._ok("No input to check")
        if len(input_text) > self.max_chars:
            return self._fail(
                f"Input too long: {len(input_text)} chars (max {self.max_chars})",
                chars=len(input_text),
            )
        token_est = len(input_text) // 4
        if token_est > self.max_tokens_estimate:
            return self._fail(
                f"Estimated {token_est} tokens exceeds limit of {self.max_tokens_estimate}",
                estimated_tokens=token_est,
            )
        return self._ok("Input length OK", chars=len(input_text),
                        estimated_tokens=token_est)


class BlockedTopicGuardrail(Guardrail):
    """Block inputs or outputs that match forbidden topic patterns."""

    name = "blocked_topic"

    def __init__(self, blocked_patterns: list[str] | None = None):
        self.blocked_patterns = blocked_patterns or [
            r"\b(bombs?|weapons?|exploit|hack)\b",
            r"\b(illegal|illicit)\s+(drug|substance)",
        ]
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.blocked_patterns]

    def check(self, *, input_text: str | None = None,
              output_text: str | None = None, **_: Any) -> GuardrailResult:
        for text, label in [(input_text, "input"), (output_text, "output")]:
            if text is None:
                continue
            for pattern in self._compiled:
                match = pattern.search(text)
                if match:
                    return self._fail(
                        f"Blocked topic detected in {label}: '{match.group()}'",
                        location=label, matched=match.group(),
                    )
        return self._ok("No blocked topics found")


class PiiDetectionGuardrail(Guardrail):
    """Detect common PII patterns (emails, phone numbers, SSNs, credit cards)."""

    name = "pii_detection"

    PII_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }

    def __init__(self, check_output: bool = True, check_input: bool = False,
                 pii_types: list[str] | None = None):
        self.check_output = check_output
        self.check_input = check_input
        types = pii_types or list(self.PII_PATTERNS.keys())
        self._patterns = {k: re.compile(v) for k, v in self.PII_PATTERNS.items()
                          if k in types}

    def check(self, *, input_text: str | None = None,
              output_text: str | None = None, **_: Any) -> GuardrailResult:
        found: list[dict[str, str]] = []
        checks = []
        if self.check_input and input_text:
            checks.append(("input", input_text))
        if self.check_output and output_text:
            checks.append(("output", output_text))

        for location, text in checks:
            for pii_type, pattern in self._patterns.items():
                if pattern.search(text):
                    found.append({"type": pii_type, "location": location})

        if found:
            types_found = ", ".join(f["type"] for f in found)
            return self._fail(f"PII detected: {types_found}", pii_found=found)
        return self._ok("No PII detected")


class OutputFormatGuardrail(Guardrail):
    """Validate that model output matches an expected format."""

    name = "output_format"

    def __init__(self, *, max_length: int = 5000,
                 required_sections: list[str] | None = None,
                 prohibited_phrases: list[str] | None = None):
        self.max_length = max_length
        self.required_sections = required_sections or []
        self.prohibited_phrases = prohibited_phrases or []

    def check(self, *, output_text: str | None = None, **_: Any) -> GuardrailResult:
        if output_text is None:
            return self._ok("No output to check")
        if len(output_text) > self.max_length:
            return self._fail(
                f"Output too long: {len(output_text)} chars (max {self.max_length})",
            )
        for section in self.required_sections:
            if section.lower() not in output_text.lower():
                return self._fail(f"Missing required section: '{section}'")
        for phrase in self.prohibited_phrases:
            if phrase.lower() in output_text.lower():
                return self._fail(f"Prohibited phrase found: '{phrase}'")
        return self._ok("Output format OK")


class CostLimitGuardrail(Guardrail):
    """Track cumulative token usage and block requests that would exceed a budget."""

    name = "cost_limit"

    def __init__(self, max_total_tokens: int = 100_000,
                 max_single_request_tokens: int = 4096):
        self.max_total_tokens = max_total_tokens
        self.max_single_request_tokens = max_single_request_tokens
        self.tokens_used: int = 0

    def record_usage(self, tokens: int) -> None:
        self.tokens_used += tokens

    def check(self, *, input_text: str | None = None, **_: Any) -> GuardrailResult:
        if self.tokens_used >= self.max_total_tokens:
            return self._fail(
                f"Token budget exhausted: {self.tokens_used}/{self.max_total_tokens}",
                tokens_used=self.tokens_used,
            )
        if input_text:
            est = len(input_text) // 4
            if est > self.max_single_request_tokens:
                return self._fail(
                    f"Single request too large: ~{est} tokens "
                    f"(max {self.max_single_request_tokens})",
                    estimated_tokens=est,
                )
        return self._ok(
            f"Budget OK: {self.tokens_used}/{self.max_total_tokens} tokens used",
            tokens_used=self.tokens_used, budget=self.max_total_tokens,
        )


class ToolCallAuditGuardrail(Guardrail):
    """Audit and restrict which tools the model is allowed to call."""

    name = "tool_call_audit"

    def __init__(self, allowed_tools: list[str] | None = None,
                 blocked_tools: list[str] | None = None,
                 max_tool_calls_per_turn: int = 5):
        self.allowed_tools = set(allowed_tools) if allowed_tools else None
        self.blocked_tools = set(blocked_tools or [])
        self.max_tool_calls_per_turn = max_tool_calls_per_turn
        self.audit_log: list[dict[str, Any]] = []

    def check(self, *, tool_calls: list[dict] | None = None, **_: Any) -> GuardrailResult:
        if not tool_calls:
            return self._ok("No tool calls to audit")

        if len(tool_calls) > self.max_tool_calls_per_turn:
            return self._fail(
                f"Too many tool calls: {len(tool_calls)} "
                f"(max {self.max_tool_calls_per_turn})",
            )

        for tc in tool_calls:
            name = tc.get("function", {}).get("name", tc.get("name", "unknown"))
            self.audit_log.append({"tool": name, "args": tc.get("function", {}).get("arguments", "")})

            if name in self.blocked_tools:
                return self._fail(f"Blocked tool called: {name}")
            if self.allowed_tools is not None and name not in self.allowed_tools:
                return self._fail(f"Tool not in allow-list: {name}")

        return self._ok(f"All {len(tool_calls)} tool call(s) approved")
