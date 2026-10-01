"""Tests for the named versions of the agent. Run with:  pytest tests/agent"""
import pytest

from src.agent.graph import run_agent
from src.agent.versions import V1, V2, VERSIONS, options_for
from src.data.models import AgentRequest


def test_v1_has_every_setting_off_and_v2_has_them_on():
    assert V1 == {"retrieval": "v1", "authoritative_only": False, "scope_to_order": False, "grounding_rule": False,
                  "amount_guard": False, "escalation_check": False}
    assert V2 == {"retrieval": "core_order", "authoritative_only": True, "scope_to_order": True,
                  "grounding_rule": True, "amount_guard": True, "escalation_check": True}
    assert V1.keys() == V2.keys() and set(VERSIONS) == {"v1", "v2"}


def test_v2_is_the_default_and_a_single_setting_can_be_overridden():
    assert options_for() == V2
    assert options_for("v1") == V1
    assert options_for("v2", escalation_check=False) == {**V2, "escalation_check": False}
    assert options_for("v2", retrieval=V1["retrieval"])["retrieval"] == "v1"


def test_unknown_versions_and_settings_are_errors():
    with pytest.raises(ValueError):
        options_for("v3")
    with pytest.raises(ValueError):
        options_for("v2", not_a_setting=True)


def test_run_agent_rejects_an_unknown_setting_before_doing_any_work():
    request = AgentRequest(order_id="NOPE-1", message="hi", today="2026-09-29")
    with pytest.raises(ValueError):
        run_agent(request, not_a_setting=True)
