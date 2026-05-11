"""
Travel Agent Demo — NVIDIA NIM with Runtime Guardrails
======================================================

A travel planning agent powered by NVIDIA Nemotron via NIM,
wrapped with configurable guardrails that enforce safety at every step.

Run:
    export NVIDIA_API_KEY=nvapi-...
    pip install openai gradio
    python examples/travel_agent_demo.py

The Gradio UI shows guardrail enforcement in real time.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nim_guardrails import (
    AgentConfig,
    BlockedTopicGuardrail,
    CostLimitGuardrail,
    GuardedAgent,
    GuardrailChain,
    InputLengthGuardrail,
    NimClient,
    OutputFormatGuardrail,
    PiiDetectionGuardrail,
    ToolCallAuditGuardrail,
    ToolDefinition,
)


# ---------------------------------------------------------------------------
# Tool definitions — things the agent can do
# ---------------------------------------------------------------------------

def search_flights(origin: str, destination: str, date: str) -> str:
    """Simulated flight search."""
    return json.dumps({
        "flights": [
            {"airline": "NIM Air", "departure": "08:00", "arrival": "14:30",
             "price": "$450", "stops": 0},
            {"airline": "GPU Express", "departure": "11:15", "arrival": "17:45",
             "price": "$380", "stops": 1},
            {"airline": "Tensor Wings", "departure": "16:00", "arrival": "22:30",
             "price": "$520", "stops": 0},
        ],
        "origin": origin, "destination": destination, "date": date,
    })


def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """Simulated hotel search."""
    return json.dumps({
        "hotels": [
            {"name": "CUDA Grand Hotel", "rating": 4.8, "price": "$180/night",
             "amenities": ["wifi", "pool", "gym"]},
            {"name": "Inference Inn", "rating": 4.5, "price": "$120/night",
             "amenities": ["wifi", "breakfast"]},
            {"name": "Parallel Suites", "rating": 4.9, "price": "$250/night",
             "amenities": ["wifi", "pool", "spa", "restaurant"]},
        ],
        "city": city, "checkin": checkin, "checkout": checkout,
    })


def get_weather(city: str, date: str) -> str:
    """Simulated weather lookup."""
    return json.dumps({
        "city": city, "date": date,
        "forecast": "Partly cloudy, 24°C / 75°F, 10% chance of rain",
        "recommendation": "Light layers recommended",
    })


TOOLS = [
    ToolDefinition(
        name="search_flights",
        description="Search for flights between two cities on a given date",
        parameters={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city"},
                "destination": {"type": "string", "description": "Arrival city"},
                "date": {"type": "string", "description": "Travel date (YYYY-MM-DD)"},
            },
            "required": ["origin", "destination", "date"],
        },
        handler=search_flights,
    ),
    ToolDefinition(
        name="search_hotels",
        description="Search for hotels in a city for given dates",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City to search"},
                "checkin": {"type": "string", "description": "Check-in date"},
                "checkout": {"type": "string", "description": "Check-out date"},
            },
            "required": ["city", "checkin", "checkout"],
        },
        handler=search_hotels,
    ),
    ToolDefinition(
        name="get_weather",
        description="Get weather forecast for a city on a specific date",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
            },
            "required": ["city", "date"],
        },
        handler=get_weather,
    ),
]


# ---------------------------------------------------------------------------
# Build the guarded agent
# ---------------------------------------------------------------------------

def create_agent() -> GuardedAgent:
    client = NimClient()

    input_chain = GuardrailChain([
        InputLengthGuardrail(max_chars=2000),
        BlockedTopicGuardrail(),
        CostLimitGuardrail(max_total_tokens=50_000),
    ])

    output_chain = GuardrailChain([
        PiiDetectionGuardrail(check_output=True),
        OutputFormatGuardrail(max_length=5000, prohibited_phrases=[
            "I cannot help", "as an AI",
        ]),
    ])

    tool_chain = GuardrailChain([
        ToolCallAuditGuardrail(
            allowed_tools=["search_flights", "search_hotels", "get_weather"],
            max_tool_calls_per_turn=3,
        ),
    ])

    config = AgentConfig(
        system_prompt=(
            "You are a travel planning assistant. Help users plan trips by "
            "searching for flights, hotels, and weather information. "
            "Be concise and helpful. Use the available tools to provide "
            "real data. Always include prices when available."
        ),
        temperature=0.6,
        max_tokens=1024,
    )

    return GuardedAgent(
        client=client,
        config=config,
        input_guardrails=input_chain,
        output_guardrails=output_chain,
        tool_guardrails=tool_chain,
        tools=TOOLS,
    )


# ---------------------------------------------------------------------------
# CLI mode
# ---------------------------------------------------------------------------

def run_cli() -> None:
    agent = create_agent()
    print("=" * 60)
    print("  NIM Travel Agent with Runtime Guardrails")
    print("  Type 'quit' to exit, 'audit' to see the audit log")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "audit":
            print(json.dumps(agent.get_audit_log(), indent=2))
            continue

        response, record = agent.run(user_input)

        if record.blocked:
            print(f"\n[GUARDRAIL] {record.block_reason}")
        else:
            print(f"\nAgent: {response}")

        # Show guardrail summary
        all_results = (
            record.input_guardrail_results
            + record.output_guardrail_results
            + record.tool_guardrail_results
        )
        passed = sum(1 for r in all_results if r.passed)
        total = len(all_results)
        latency = record.latency_ms
        print(f"  [{passed}/{total} guardrails passed | {latency:.0f}ms]")


# ---------------------------------------------------------------------------
# Gradio UI mode
# ---------------------------------------------------------------------------

def run_gradio() -> None:
    try:
        import gradio as gr
    except ImportError:
        print("Gradio not installed. Install with: pip install gradio")
        print("Falling back to CLI mode.\n")
        run_cli()
        return

    agent = create_agent()

    def chat(message: str, history: list) -> tuple:
        response, record = agent.run(message)

        # Build guardrail status display
        all_results = (
            record.input_guardrail_results
            + record.output_guardrail_results
            + record.tool_guardrail_results
        )
        guardrail_lines = []
        for r in all_results:
            icon = "PASS" if r.passed else "FAIL"
            guardrail_lines.append(f"[{icon}] {r.guardrail_name}: {r.message}")

        status = "\n".join(guardrail_lines)
        status += f"\n\nLatency: {record.latency_ms:.0f}ms"
        if record.nim_response and record.nim_response.usage:
            tokens = record.nim_response.usage.get("total_tokens", 0)
            status += f" | Tokens: {tokens}"

        audit = json.dumps(agent.get_audit_log(), indent=2)

        return response, status, audit

    with gr.Blocks(title="NIM Agent Guardrails") as demo:
        gr.Markdown("# NIM Travel Agent with Runtime Guardrails")
        gr.Markdown(
            "A travel planning agent powered by **NVIDIA Nemotron via NIM**, "
            "with configurable guardrails enforced at every step."
        )

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(height=400, type="messages")
                msg = gr.Textbox(
                    placeholder="Plan a trip to Tokyo next month...",
                    label="Your message",
                )
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    clear = gr.Button("Clear")

            with gr.Column(scale=1):
                guardrail_status = gr.Textbox(
                    label="Guardrail Status", lines=12, interactive=False,
                )
                audit_log = gr.Code(
                    label="Audit Log (JSON)", language="json",
                )

        def respond(message: str, chat_history: list):
            response, status, audit = chat(message, chat_history)
            chat_history = chat_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ]
            return "", chat_history, status, audit

        send.click(respond, [msg, chatbot],
                    [msg, chatbot, guardrail_status, audit_log])
        msg.submit(respond, [msg, chatbot],
                   [msg, chatbot, guardrail_status, audit_log])
        clear.click(lambda: ([], "", ""), outputs=[chatbot, guardrail_status,
                                                    audit_log])

    demo.launch()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--gradio" in sys.argv:
        run_gradio()
    else:
        run_cli()
