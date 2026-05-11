"""Thin wrapper around NVIDIA NIM's OpenAI-compatible chat completions API."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]


NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"


@dataclass
class NimResponse:
    """Structured response from a NIM API call."""
    content: str
    model: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    raw: Any = None


class NimClient:
    """Client for NVIDIA NIM inference via the OpenAI-compatible endpoint.

    Requires either ``openai`` package installed or falls back to ``urllib``.
    Set ``NVIDIA_API_KEY`` in your environment.
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 base_url: str = NIM_BASE_URL):
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        self.model = model
        self.base_url = base_url

        if not self.api_key:
            raise ValueError(
                "NVIDIA_API_KEY not set. Pass api_key= or set the env var."
            )

        if OpenAI is not None:
            self._openai = OpenAI(base_url=self.base_url, api_key=self.api_key)
        else:
            self._openai = None

    def chat(self, messages: list[dict[str, str]],
             tools: list[dict] | None = None,
             temperature: float = 0.7,
             max_tokens: int = 1024) -> NimResponse:
        """Send a chat completion request to NIM."""
        t0 = time.perf_counter()

        if self._openai is not None:
            return self._chat_openai(messages, tools, temperature, max_tokens, t0)
        return self._chat_urllib(messages, tools, temperature, max_tokens, t0)

    # -- OpenAI SDK path ------------------------------------------------------

    def _chat_openai(self, messages: list[dict], tools: list[dict] | None,
                     temperature: float, max_tokens: int,
                     t0: float) -> NimResponse:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        resp = self._openai.chat.completions.create(**kwargs)
        latency = (time.perf_counter() - t0) * 1000

        choice = resp.choices[0]
        tool_calls_raw = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls_raw.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                })

        return NimResponse(
            content=choice.message.content or "",
            model=resp.model,
            tool_calls=tool_calls_raw,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0,
            },
            latency_ms=latency,
            raw=resp,
        )

    # -- urllib fallback -------------------------------------------------------

    def _chat_urllib(self, messages: list[dict], tools: list[dict] | None,
                     temperature: float, max_tokens: int,
                     t0: float) -> NimResponse:
        import urllib.request

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools

        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())

        latency = (time.perf_counter() - t0) * 1000
        choice = result["choices"][0]
        return NimResponse(
            content=choice["message"].get("content", ""),
            model=result.get("model", self.model),
            tool_calls=choice["message"].get("tool_calls", []),
            usage=result.get("usage", {}),
            latency_ms=latency,
            raw=result,
        )
