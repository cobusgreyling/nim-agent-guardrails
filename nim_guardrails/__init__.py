"""nim-agent-guardrails — Runtime safety layer for NVIDIA NIM-powered agents."""

from nim_guardrails.guardrails import (
    Guardrail,
    GuardrailResult,
    GuardrailChain,
    InputLengthGuardrail,
    BlockedTopicGuardrail,
    PiiDetectionGuardrail,
    OutputFormatGuardrail,
    CostLimitGuardrail,
    ToolCallAuditGuardrail,
)
from nim_guardrails.client import NimClient, NimResponse
from nim_guardrails.agent import GuardedAgent, AgentConfig, ToolDefinition

__version__ = "0.2.0"

__all__ = [
    "Guardrail",
    "GuardrailResult",
    "GuardrailChain",
    "InputLengthGuardrail",
    "BlockedTopicGuardrail",
    "PiiDetectionGuardrail",
    "OutputFormatGuardrail",
    "CostLimitGuardrail",
    "ToolCallAuditGuardrail",
    "NimClient",
    "NimResponse",
    "GuardedAgent",
    "AgentConfig",
    "ToolDefinition",
]
