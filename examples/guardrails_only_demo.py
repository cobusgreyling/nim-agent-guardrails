"""
Guardrails-Only Demo — no API key needed
=========================================

Shows the guardrail chain working independently of NIM.
Useful for testing guardrail configurations before deploying.

Run:
    python examples/guardrails_only_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nim_guardrails import (
    BlockedTopicGuardrail,
    CostLimitGuardrail,
    GuardrailChain,
    InputLengthGuardrail,
    OutputFormatGuardrail,
    PiiDetectionGuardrail,
    ToolCallAuditGuardrail,
)


def main() -> None:
    print("=" * 60)
    print("  Guardrails-Only Demo (no API key needed)")
    print("=" * 60)

    # Build guardrail chains
    input_chain = GuardrailChain([
        InputLengthGuardrail(max_chars=500),
        BlockedTopicGuardrail(),
        CostLimitGuardrail(max_total_tokens=10_000),
    ])

    output_chain = GuardrailChain([
        PiiDetectionGuardrail(check_output=True),
        OutputFormatGuardrail(max_length=2000, prohibited_phrases=["as an AI"]),
    ])

    tool_chain = GuardrailChain([
        ToolCallAuditGuardrail(
            allowed_tools=["search_flights", "get_weather"],
            max_tool_calls_per_turn=2,
        ),
    ])

    # -- Test cases ----------------------------------------------------------

    tests = [
        {
            "name": "Normal input",
            "chain": "input",
            "kwargs": {"input_text": "Plan a trip to Paris for next weekend"},
        },
        {
            "name": "Input too long",
            "chain": "input",
            "kwargs": {"input_text": "x" * 600},
        },
        {
            "name": "Blocked topic in input",
            "chain": "input",
            "kwargs": {"input_text": "How do I exploit the system?"},
        },
        {
            "name": "Clean output",
            "chain": "output",
            "kwargs": {"output_text": "Here are your flight options for Paris."},
        },
        {
            "name": "Output with PII (email)",
            "chain": "output",
            "kwargs": {"output_text": "Contact us at support@airline.com for help."},
        },
        {
            "name": "Output with prohibited phrase",
            "chain": "output",
            "kwargs": {"output_text": "As an AI, I cannot book flights directly."},
        },
        {
            "name": "Allowed tool call",
            "chain": "tool",
            "kwargs": {
                "tool_calls": [
                    {"function": {"name": "search_flights",
                                  "arguments": '{"origin":"NYC","destination":"PAR"}'}}
                ]
            },
        },
        {
            "name": "Blocked tool call",
            "chain": "tool",
            "kwargs": {
                "tool_calls": [
                    {"function": {"name": "delete_account",
                                  "arguments": '{"user_id":"123"}'}}
                ]
            },
        },
        {
            "name": "Too many tool calls",
            "chain": "tool",
            "kwargs": {
                "tool_calls": [
                    {"function": {"name": "search_flights", "arguments": "{}"}},
                    {"function": {"name": "get_weather", "arguments": "{}"}},
                    {"function": {"name": "search_flights", "arguments": "{}"}},
                ]
            },
        },
    ]

    chains = {"input": input_chain, "output": output_chain, "tool": tool_chain}

    for test in tests:
        chain = chains[test["chain"]]
        results = chain.run(**test["kwargs"])
        all_passed = chain.all_passed(results)
        icon = "PASS" if all_passed else "FAIL"

        print(f"\n[{icon}] {test['name']}")
        for r in results:
            status = "pass" if r.passed else "FAIL"
            print(f"  {r.guardrail_name}: {status} — {r.message}")

    print("\n" + "=" * 60)
    print("  All tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
