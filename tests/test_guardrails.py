"""Tests for guardrails — no NIM API key required."""

import pytest

from nim_guardrails.guardrails import (
    BlockedTopicGuardrail,
    CostLimitGuardrail,
    GuardrailChain,
    InputLengthGuardrail,
    OutputFormatGuardrail,
    PiiDetectionGuardrail,
    ToolCallAuditGuardrail,
)


# ---------------------------------------------------------------------------
# InputLengthGuardrail
# ---------------------------------------------------------------------------

class TestInputLength:
    def test_short_input_passes(self):
        g = InputLengthGuardrail(max_chars=100)
        r = g.check(input_text="Hello world")
        assert r.passed

    def test_long_input_fails(self):
        g = InputLengthGuardrail(max_chars=10)
        r = g.check(input_text="This is way too long")
        assert not r.passed
        assert "too long" in r.message

    def test_none_input_passes(self):
        g = InputLengthGuardrail()
        r = g.check(input_text=None)
        assert r.passed

    def test_token_estimate_limit(self):
        g = InputLengthGuardrail(max_chars=100_000, max_tokens_estimate=10)
        r = g.check(input_text="x" * 200)  # ~50 tokens
        assert not r.passed
        assert "tokens" in r.message


# ---------------------------------------------------------------------------
# BlockedTopicGuardrail
# ---------------------------------------------------------------------------

class TestBlockedTopic:
    def test_clean_input_passes(self):
        g = BlockedTopicGuardrail()
        r = g.check(input_text="Plan a trip to Tokyo")
        assert r.passed

    def test_blocked_word_in_input(self):
        g = BlockedTopicGuardrail()
        r = g.check(input_text="How do I exploit this?")
        assert not r.passed
        assert "exploit" in r.message

    def test_blocked_word_in_output(self):
        g = BlockedTopicGuardrail()
        r = g.check(output_text="You could use a weapon for that")
        assert not r.passed

    def test_custom_patterns(self):
        g = BlockedTopicGuardrail(blocked_patterns=[r"\bpassword\b"])
        assert not g.check(input_text="What is the password?").passed
        assert g.check(input_text="What is the plan?").passed

    def test_case_insensitive(self):
        g = BlockedTopicGuardrail()
        r = g.check(input_text="Tell me about WEAPONS")
        assert not r.passed


# ---------------------------------------------------------------------------
# PiiDetectionGuardrail
# ---------------------------------------------------------------------------

class TestPiiDetection:
    def test_no_pii_passes(self):
        g = PiiDetectionGuardrail()
        r = g.check(output_text="Here are your flight options.")
        assert r.passed

    def test_email_detected(self):
        g = PiiDetectionGuardrail()
        r = g.check(output_text="Contact john@example.com")
        assert not r.passed
        assert "email" in r.message

    def test_phone_detected(self):
        g = PiiDetectionGuardrail()
        r = g.check(output_text="Call 555-123-4567")
        assert not r.passed

    def test_ssn_detected(self):
        g = PiiDetectionGuardrail()
        r = g.check(output_text="SSN: 123-45-6789")
        assert not r.passed

    def test_credit_card_detected(self):
        g = PiiDetectionGuardrail()
        r = g.check(output_text="Card: 4111 1111 1111 1111")
        assert not r.passed

    def test_input_check_when_enabled(self):
        g = PiiDetectionGuardrail(check_input=True)
        r = g.check(input_text="My email is test@test.com")
        assert not r.passed

    def test_input_not_checked_by_default(self):
        g = PiiDetectionGuardrail()
        r = g.check(input_text="My email is test@test.com")
        assert r.passed  # input not checked by default

    def test_selective_pii_types(self):
        g = PiiDetectionGuardrail(pii_types=["ssn"])
        assert g.check(output_text="Email: test@test.com").passed  # email not checked
        assert not g.check(output_text="SSN: 123-45-6789").passed


# ---------------------------------------------------------------------------
# OutputFormatGuardrail
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_clean_output_passes(self):
        g = OutputFormatGuardrail()
        r = g.check(output_text="Here are your results.")
        assert r.passed

    def test_too_long_output(self):
        g = OutputFormatGuardrail(max_length=10)
        r = g.check(output_text="This is way too long for the limit")
        assert not r.passed

    def test_missing_required_section(self):
        g = OutputFormatGuardrail(required_sections=["## Summary"])
        r = g.check(output_text="Just some text without a summary")
        assert not r.passed

    def test_required_section_present(self):
        g = OutputFormatGuardrail(required_sections=["summary"])
        r = g.check(output_text="Here is a summary of your trip.")
        assert r.passed

    def test_prohibited_phrase(self):
        g = OutputFormatGuardrail(prohibited_phrases=["as an AI"])
        r = g.check(output_text="As an AI, I can help you plan.")
        assert not r.passed

    def test_none_output_passes(self):
        g = OutputFormatGuardrail()
        r = g.check(output_text=None)
        assert r.passed


# ---------------------------------------------------------------------------
# CostLimitGuardrail
# ---------------------------------------------------------------------------

class TestCostLimit:
    def test_under_budget_passes(self):
        g = CostLimitGuardrail(max_total_tokens=1000)
        r = g.check(input_text="Hello")
        assert r.passed

    def test_budget_exhausted(self):
        g = CostLimitGuardrail(max_total_tokens=100)
        g.record_usage(100)
        r = g.check(input_text="Hello")
        assert not r.passed
        assert "exhausted" in r.message

    def test_single_request_too_large(self):
        g = CostLimitGuardrail(max_single_request_tokens=10)
        r = g.check(input_text="x" * 200)  # ~50 tokens
        assert not r.passed

    def test_cumulative_tracking(self):
        g = CostLimitGuardrail(max_total_tokens=100)
        g.record_usage(50)
        assert g.check(input_text="Hi").passed
        g.record_usage(50)
        assert not g.check(input_text="Hi").passed


# ---------------------------------------------------------------------------
# ToolCallAuditGuardrail
# ---------------------------------------------------------------------------

class TestToolCallAudit:
    def _tc(self, name: str, args: str = "{}") -> dict:
        return {"function": {"name": name, "arguments": args}}

    def test_allowed_tool_passes(self):
        g = ToolCallAuditGuardrail(allowed_tools=["search"])
        r = g.check(tool_calls=[self._tc("search")])
        assert r.passed

    def test_blocked_tool_fails(self):
        g = ToolCallAuditGuardrail(blocked_tools=["delete"])
        r = g.check(tool_calls=[self._tc("delete")])
        assert not r.passed

    def test_tool_not_in_allowlist(self):
        g = ToolCallAuditGuardrail(allowed_tools=["search"])
        r = g.check(tool_calls=[self._tc("delete")])
        assert not r.passed

    def test_too_many_tool_calls(self):
        g = ToolCallAuditGuardrail(max_tool_calls_per_turn=2)
        r = g.check(tool_calls=[self._tc("a"), self._tc("b"), self._tc("c")])
        assert not r.passed

    def test_no_tool_calls_passes(self):
        g = ToolCallAuditGuardrail()
        r = g.check(tool_calls=None)
        assert r.passed

    def test_audit_log_populated(self):
        g = ToolCallAuditGuardrail()
        g.check(tool_calls=[self._tc("search", '{"q":"paris"}')])
        assert len(g.audit_log) == 1
        assert g.audit_log[0]["tool"] == "search"


# ---------------------------------------------------------------------------
# GuardrailChain
# ---------------------------------------------------------------------------

class TestGuardrailChain:
    def test_all_pass(self):
        chain = GuardrailChain([
            InputLengthGuardrail(max_chars=1000),
            BlockedTopicGuardrail(),
        ])
        results = chain.run(input_text="Plan a trip to Paris")
        assert chain.all_passed(results)
        assert len(results) == 2

    def test_short_circuit_on_failure(self):
        chain = GuardrailChain([
            InputLengthGuardrail(max_chars=5),  # will fail
            BlockedTopicGuardrail(),  # should not run
        ])
        results = chain.run(input_text="This is a long input")
        assert not chain.all_passed(results)
        assert len(results) == 1  # short-circuited

    def test_add_method(self):
        chain = GuardrailChain()
        chain.add(InputLengthGuardrail()).add(BlockedTopicGuardrail())
        assert len(chain.guardrails) == 2

    def test_empty_chain_passes(self):
        chain = GuardrailChain()
        results = chain.run(input_text="anything")
        assert chain.all_passed(results)
        assert len(results) == 0
