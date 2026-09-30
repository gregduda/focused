"""Graph tests. Run with:  pytest tests/agent

Everything except the last test runs without calling the model. The last test calls the OpenAI API and
sends a trace to LangSmith (a few cents), and only checks the shape of the result, not whether the decision is
right; correctness is measured in the evals."""
from datetime import date
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage

from src.agent.graph import build_graph, route_after_agent, route_decision, run_agent
from src.agent.nodes import order_not_found, record_approval, record_denial, record_escalation
from src.agent.state import AgentDecision
from src.data.models import AgentRequest
from src.data.order_database import OrderDatabase

TODAY = date(2026, 9, 29)
ORDER_DB = OrderDatabase()


def decision_args(**overrides) -> dict:
    args = {"decision": "APPROVE", "rationale": "r", "customer_message": "m"}
    return {**args, **overrides}


def ai_message(*calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"call_{i}"} for i, (n, a) in enumerate(calls)])




# --- wiring and routing -------------------------------------------------------------------------------

def test_graph_has_the_planned_nodes():
    nodes = set(build_graph().get_graph().nodes)
    assert {"load_order", "order_not_found", "retrieve", "agent", "tools", "decide",
            "record_approval", "record_escalation", "record_denial"} <= nodes
    assert not {"nudge", "read_decision", "finalize", "finish"} & nodes


def test_route_after_agent():
    assert route_after_agent({"messages": [ai_message(("compute_refund", {}))]}) == "tools"
    assert route_after_agent({"messages": [AIMessage(content="Analysis: within the window; approve.")]}) == "decide"


@pytest.mark.parametrize("label,expected", [("APPROVE", "record_approval"), ("ESCALATE", "record_escalation"),
                                            ("DENY", "record_denial")])
def test_route_decision(label, expected):
    assert route_decision({"decision": AgentDecision(**decision_args(decision=label))}) == expected


# --- record nodes -------------------------------------------------------------------------------------

def test_record_approval_records_the_chosen_action():
    state = {"order": ORDER_DB.get_order("JP-1001"),
             "decision": AgentDecision(**decision_args(approved_action="create_rma", refund_amount="121.65",
                                                       refund_method="original"))}
    (action,) = record_approval(state)["actions"]
    assert (action.type, action.order_id, action.item_id) == ("create_rma", "JP-1001", "IT-1001")
    assert action.refund_amount == Decimal("121.65") and action.refund_method == "original"


def test_record_approval_for_a_cancellation_has_no_item():
    state = {"order": ORDER_DB.get_order("JP-1007"),
             "decision": AgentDecision(**decision_args(approved_action="cancel_order", refund_amount="90.90"))}
    (action,) = record_approval(state)["actions"]
    assert action.type == "cancel_order" and action.item_id is None


@pytest.mark.parametrize("action_type", ["create_exchange", "create_reshipment", "create_replacement"])
def test_record_approval_for_actions_without_an_amount(action_type):
    state = {"order": ORDER_DB.get_order("JP-1004"),
             "decision": AgentDecision(**decision_args(approved_action=action_type))}
    (action,) = record_approval(state)["actions"]
    assert (action.type, action.item_id, action.refund_amount) == (action_type, "IT-1004", None)


def test_record_approval_without_an_action_records_nothing():
    state = {"order": ORDER_DB.get_order("JP-1001"), "decision": AgentDecision(**decision_args())}
    assert record_approval(state) == {"actions": []}


def test_record_escalation_records_type_reason_and_docs():
    state = {"order": ORDER_DB.get_order("JP-1009"),
             "decision": AgentDecision(**decision_args(decision="ESCALATE", escalation_type="high_value",
                                                       rationale="Jewelry over the limit.", cited_doc_ids=["CAT-06"]))}
    (action,) = record_escalation(state)["actions"]
    assert (action.type, action.escalation_type, action.docs_consulted) == ("open_escalation", "high_value", ["CAT-06"])


def test_record_denial_records_reason_and_docs():
    state = {"order": ORDER_DB.get_order("JP-1001"),
             "decision": AgentDecision(**decision_args(decision="DENY", rationale="Past the window.",
                                                       cited_doc_ids=["POL-02"]))}
    (action,) = record_denial(state)["actions"]
    assert (action.type, action.order_id, action.reason, action.docs_consulted) == (
        "record_denial", "JP-1001", "Past the window.", ["POL-02"])


def test_record_escalation_defaults_the_type_to_standard():
    state = {"order": ORDER_DB.get_order("JP-1001"),
             "decision": AgentDecision(**decision_args(decision="ESCALATE"))}
    assert record_escalation(state)["actions"][0].escalation_type == "standard"


def test_order_not_found_returns_an_escalation_decision_and_action():
    out = order_not_found({"request": AgentRequest(order_id="NOPE-1", message="hi", today=TODAY)})
    assert out["decision"].decision == "ESCALATE" and out["decision"].escalation_type == "order_not_found"
    assert [a.type for a in out["actions"]] == ["open_escalation"]


# --- whole runs ---------------------------------------------------------------------------------------

def test_unknown_order_escalates_without_calling_the_llm():
    result = run_agent(AgentRequest(order_id="NOPE-1", message="Refund me please", today=TODAY))
    assert result.decision == "ESCALATE" and result.escalation_type == "order_not_found"
    assert [a.type for a in result.actions] == ["open_escalation"]
    assert "order" in result.customer_message.lower()


def test_end_to_end_return_request():
    request = AgentRequest(order_id="JP-1001", today=TODAY,
                           message="Hi, the jacket I bought doesn't fit. I never wore it and the tags are on. "
                                   "I'd like to send it back for a refund.")
    result = run_agent(request)
    print("\n", result.model_dump_json(indent=2))
    assert result.decision in {"APPROVE", "DENY", "ESCALATE"} and result.customer_message
    assert len(result.actions) <= 1  # one recorded entry per run (none only for an APPROVE with no approved_action)
    if result.decision == "DENY":
        assert [a.type for a in result.actions] == ["record_denial"]
    if result.decision == "ESCALATE":
        assert [a.type for a in result.actions] == ["open_escalation"]
