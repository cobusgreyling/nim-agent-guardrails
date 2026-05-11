"""GuardedAgent — an agent that wraps every NIM call with guardrail checks."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from nim_guardrails.client import NimClient, NimResponse
from nim_guardrails.guardrails import (
    CostLimitGuardrail,
    GuardrailChain,
    GuardrailResult,
)


@dataclass
class ToolDefinition:
    """Defines a tool the agent can call."""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class AgentConfig:
    """Configuration for a GuardedAgent."""
    system_prompt: str = "You are a helpful assistant."
    model: str = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    temperature: float = 0.7
    max_tokens: int = 1024
    max_turns: int = 10


@dataclass
class TurnRecord:
    """Record of a single agent turn with guardrail results."""
    turn_number: int
    user_input: str | None
    input_guardrail_results: list[GuardrailResult]
    nim_response: NimResponse | None
    output_guardrail_results: list[GuardrailResult]
    tool_guardrail_results: list[GuardrailResult]
    blocked: bool
    block_reason: str = ""
    latency_ms: float = 0.0


class GuardedAgent:
    """Agent that enforces guardrails before and after every NIM call.

    Usage::

        agent = GuardedAgent(
            client=NimClient(),
            input_guardrails=input_chain,
            output_guardrails=output_chain,
            tool_guardrails=tool_chain,
        )
        response, record = agent.run("Plan a trip to Tokyo")
    """

    def __init__(
        self,
        client: NimClient,
        config: AgentConfig | None = None,
        input_guardrails: GuardrailChain | None = None,
        output_guardrails: GuardrailChain | None = None,
        tool_guardrails: GuardrailChain | None = None,
        tools: list[ToolDefinition] | None = None,
    ):
        self.client = client
        self.config = config or AgentConfig()
        self.input_guardrails = input_guardrails or GuardrailChain()
        self.output_guardrails = output_guardrails or GuardrailChain()
        self.tool_guardrails = tool_guardrails or GuardrailChain()
        self.tools = {t.name: t for t in (tools or [])}
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt}
        ]
        self.history: list[TurnRecord] = []
        self._turn = 0

    def run(self, user_input: str) -> tuple[str, TurnRecord]:
        """Execute one agent turn with full guardrail enforcement."""
        t0 = time.perf_counter()
        self._turn += 1

        # -- Input guardrails --------------------------------------------------
        input_results = self.input_guardrails.run(input_text=user_input)
        if not self.input_guardrails.all_passed(input_results):
            reason = next(r.message for r in input_results if not r.passed)
            record = TurnRecord(
                turn_number=self._turn, user_input=user_input,
                input_guardrail_results=input_results,
                nim_response=None, output_guardrail_results=[],
                tool_guardrail_results=[], blocked=True,
                block_reason=f"Input blocked: {reason}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
            self.history.append(record)
            return f"[BLOCKED] {reason}", record

        # -- Call NIM ----------------------------------------------------------
        self.messages.append({"role": "user", "content": user_input})
        openai_tools = [t.to_openai_tool() for t in self.tools.values()] or None
        nim_resp = self.client.chat(
            messages=self.messages,
            tools=openai_tools,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # -- Tool call guardrails + execution ----------------------------------
        tool_results: list[GuardrailResult] = []
        if nim_resp.tool_calls:
            tool_results = self.tool_guardrails.run(tool_calls=nim_resp.tool_calls)
            if not self.tool_guardrails.all_passed(tool_results):
                reason = next(r.message for r in tool_results if not r.passed)
                record = TurnRecord(
                    turn_number=self._turn, user_input=user_input,
                    input_guardrail_results=input_results,
                    nim_response=nim_resp, output_guardrail_results=[],
                    tool_guardrail_results=tool_results, blocked=True,
                    block_reason=f"Tool call blocked: {reason}",
                    latency_ms=(time.perf_counter() - t0) * 1000,
                )
                self.history.append(record)
                return f"[BLOCKED] {reason}", record

            # Execute approved tool calls
            self.messages.append({
                "role": "assistant",
                "content": nim_resp.content,
                "tool_calls": nim_resp.tool_calls,
            })
            for tc in nim_resp.tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                handler = self.tools.get(fn_name)
                if handler:
                    result = handler.handler(**fn_args)
                else:
                    result = f"Error: tool '{fn_name}' not found"
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Get final response after tool execution
            nim_resp = self.client.chat(
                messages=self.messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

        # -- Output guardrails -------------------------------------------------
        output_results = self.output_guardrails.run(output_text=nim_resp.content)
        if not self.output_guardrails.all_passed(output_results):
            reason = next(r.message for r in output_results if not r.passed)
            record = TurnRecord(
                turn_number=self._turn, user_input=user_input,
                input_guardrail_results=input_results,
                nim_response=nim_resp, output_guardrail_results=output_results,
                tool_guardrail_results=tool_results, blocked=True,
                block_reason=f"Output blocked: {reason}",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )
            self.history.append(record)
            return f"[BLOCKED] {reason}", record

        # -- Record cost -------------------------------------------------------
        for g in self.input_guardrails.guardrails:
            if isinstance(g, CostLimitGuardrail) and nim_resp.usage:
                g.record_usage(nim_resp.usage.get("total_tokens", 0))

        # -- Success -----------------------------------------------------------
        self.messages.append({"role": "assistant", "content": nim_resp.content})
        record = TurnRecord(
            turn_number=self._turn, user_input=user_input,
            input_guardrail_results=input_results,
            nim_response=nim_resp, output_guardrail_results=output_results,
            tool_guardrail_results=tool_results, blocked=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
        self.history.append(record)
        return nim_resp.content, record

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Return a structured audit log of all turns."""
        log = []
        for rec in self.history:
            entry: dict[str, Any] = {
                "turn": rec.turn_number,
                "blocked": rec.blocked,
                "latency_ms": round(rec.latency_ms, 1),
            }
            if rec.block_reason:
                entry["block_reason"] = rec.block_reason
            if rec.nim_response:
                entry["model"] = rec.nim_response.model
                entry["usage"] = rec.nim_response.usage
                entry["nim_latency_ms"] = round(rec.nim_response.latency_ms, 1)
            entry["guardrails"] = {
                "input": [{"name": r.guardrail_name, "passed": r.passed,
                           "message": r.message} for r in rec.input_guardrail_results],
                "output": [{"name": r.guardrail_name, "passed": r.passed,
                            "message": r.message} for r in rec.output_guardrail_results],
                "tool": [{"name": r.guardrail_name, "passed": r.passed,
                          "message": r.message} for r in rec.tool_guardrail_results],
            }
            log.append(entry)
        return log
