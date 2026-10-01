"""Graph tests. Run with:  pytest tests/agent

Everything except the last test runs without calling the model. The last test calls the OpenAI API and
sends a trace to LangSmith (a few cents), and only checks the shape of the result, not whether the decision is
right; correctness is measured in the evals."""
import json
from datetime import date
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage

from langgraph.graph import END, START, MessagesState, StateGraph

from src.agent.graph import build_graph, make_tool_node, route_after_agent, route_decision, run_agent
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
    assert {"load_order", "order_not_found", "retrieve", "agent", "tools", "escalation_check", "decide",
            "record_approval", "record_escalation", "record_denial"} <= nodes
    assert not {"nudge", "read_decision", "finalize", "finish"} & nodes


def test_route_after_agent():
    assert route_after_agent({"messages": [ai_message(("compute_refund", {}))]}) == "tools"
    assert route_after_agent({"messages": [AIMessage(content="Analysis: within the window; approve.")]}) == "escalation_check"


def test_a_calculator_error_goes_back_to_the_model_instead_of_crashing_the_run():
    """The baseline had a run die on `ValueError: at least one window is required` (a cancellation has no
    delivery date). A ToolNode only runs inside a graph here, so use a one-node graph with the real tool node."""
    g = StateGraph(MessagesState)
    g.add_node("tools", make_tool_node())
    g.add_edge(START, "tools")
    g.add_edge("tools", END)
    call = ai_message(("compute_deadline", {"start": "2026-09-02", "today": "2026-09-29", "windows": []}))
    reply = g.compile().invoke({"messages": [call]})["messages"][-1]
    assert reply.status == "error" and "at least one window is required" in reply.content


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
    assert result.retrieved == []  # the run stops before retrieval
    assert "order" in result.customer_message.lower()


def test_end_to_end_return_request():
    request = AgentRequest(order_id="JP-1001", today=TODAY,
                           message="Hi, the jacket I bought doesn't fit. I never wore it and the tags are on. "
                                   "I'd like to send it back for a refund.")
    result = run_agent(request)
    print("\n", result.model_dump_json(indent=2))
    assert result.decision in {"APPROVE", "DENY", "ESCALATE"} and result.customer_message
    assert result.retrieved  # retrieval ran and its chunks are on the result
    assert len(result.actions) <= 1  # one recorded entry per run (none only for an APPROVE with no approved_action)
    if result.decision == "DENY":
        assert [a.type for a in result.actions] == ["record_denial"]
    if result.decision == "ESCALATE":
        assert [a.type for a in result.actions] == ["open_escalation"]


def test_the_grounding_rule_is_added_to_the_prompt_only_when_asked_for():
    from src.agent.prompts import GROUNDING_RULE, SYSTEM_PROMPT, build_prefix
    from src.data.models import Customer
    order = ORDER_DB.get_order("JP-1001")
    state = {"request": AgentRequest(order_id="JP-1001", message="m", today=TODAY), "order": order,
             "customer": ORDER_DB.get_customer(order.customer_id), "chunks": []}
    assert build_prefix(state)[0].content == SYSTEM_PROMPT  # the default prompt is unchanged
    assert build_prefix(state, grounding=True)[0].content == SYSTEM_PROMPT + "\n\n" + GROUNDING_RULE


# --- the amount guard (D-074) -------------------------------------------------------------------------

def calc_message(total: str, name: str = "compute_refund", status: str = "success"):
    from langchain_core.messages import ToolMessage
    return ToolMessage(content=json.dumps({"refund_total": total, "total_to_customer": total}), name=name,
                       tool_call_id="x", status=status)


def test_the_guard_replaces_an_amount_that_is_not_a_calculator_result():
    from src.agent.nodes import correct_refund
    decision = AgentDecision(**decision_args(refund_amount="187.00"))
    fixed, note = correct_refund(decision, [calc_message("217.00")])
    assert fixed.refund_amount == "217.00" and "187.00" in note and "217.00" in note
    assert decision.refund_amount == "187.00"  # the original object is not changed


def test_the_guard_uses_the_last_calculator_total_when_there_are_several():
    from src.agent.nodes import correct_refund
    fixed, _ = correct_refund(AgentDecision(**decision_args(refund_amount="1.00")),
                              [calc_message("100.00"), calc_message("90.00")])
    assert fixed.refund_amount == "90.00"


@pytest.mark.parametrize("args,messages", [
    ({"refund_amount": "217.00"}, [calc_message("217.00")]),                       # already a calculator result
    ({"refund_amount": "100.00"}, [calc_message("100.00"), calc_message("90.00")]),  # an earlier scenario is allowed
    ({"refund_amount": None}, [calc_message("217.00")]),                            # no amount to check
    ({"refund_amount": "187.00"}, []),                                              # no calculator call at all
    ({"refund_amount": "187.00"}, [calc_message("217.00", name="compute_deadline")]),  # a different tool
    ({"refund_amount": "187.00"}, [calc_message("217.00", status="error")]),       # a failed call is not trusted
])
def test_the_guard_leaves_everything_else_alone(args, messages):
    from src.agent.nodes import correct_refund
    decision = AgentDecision(**decision_args(**args))
    assert correct_refund(decision, messages) == (decision, None)


# --- the escalation check (D-080) ---------------------------------------------------------------------

def check_state(**customer_overrides):
    from src.agent.state import RetrievedChunk
    order = ORDER_DB.get_order("JP-1011")  # the customer with 4 recent returns
    customer = ORDER_DB.get_customer(order.customer_id).model_copy(update=customer_overrides)
    chunk = RetrievedChunk(doc_id="OPS-03", section="Thresholds", status="active", authority="authoritative",
                           distance=0.0, text="Escalate when a customer has 4 or more returns.")
    return {"request": AgentRequest(order_id="JP-1011", message="Please refund my jacket.", today=TODAY), "order": order,
            "customer": customer, "chunks": [chunk], "messages": [calc_message("56.85")]}


def test_the_escalation_check_input_has_the_facts_and_the_excerpts_but_no_personal_details():
    from src.agent.prompts import ESCALATION_CHECK_PROMPT, build_escalation_check_input
    system, human = build_escalation_check_input(check_state())
    assert system.content == ESCALATION_CHECK_PROMPT
    text = human.content
    assert "returns_last_60d" in text and "4 or more returns" in text and "total_to_customer" in text
    assert "Please refund my jacket." in text
    assert "lee.kim@example.com" not in text and "Kim" not in text  # email and last name are left out


def test_the_escalation_check_does_nothing_unless_switched_on():
    from src.agent.nodes import escalation_check
    assert escalation_check(check_state(), {"configurable": {}}) == {}
    assert escalation_check(check_state(), {"configurable": {"escalation_check": False}}) == {}


def test_the_finding_tells_the_decision_step_to_escalate_without_naming_the_rule_to_the_customer():
    from src.agent.prompts import escalation_finding_message
    text = escalation_finding_message("OPS-03", "loss_prevention", "4 returns in 60 days")
    assert "ESCALATE" in text and "OPS-03" in text and "loss_prevention" in text
    assert "do not mention the rule" in text


def test_the_graph_runs_the_check_before_the_decision():
    graph = build_graph().get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("escalation_check", "decide") in edges and ("agent", "escalation_check") in edges
    assert ("agent", "decide") not in edges


@pytest.mark.parametrize("label", ["DENY", "ESCALATE"])
def test_the_guard_clears_a_refund_amount_left_on_a_decision_that_is_not_an_approval(label):
    from src.agent.nodes import correct_refund
    decision = AgentDecision(**decision_args(decision=label, refund_amount="128.75"))
    fixed, note = correct_refund(decision, [calc_message("128.75")])
    assert fixed.refund_amount is None and label in note and "128.75" in note
    assert correct_refund(AgentDecision(**decision_args(decision=label)), []) == (AgentDecision(**decision_args(decision=label)), None)


def test_the_grounding_rule_limits_escalating_to_ask_for_details():
    from src.agent.prompts import GROUNDING_RULE
    assert "replaces the earlier instruction about needing more information" in GROUNDING_RULE
    assert "Do not escalate to ask for details the excerpts do not require" in GROUNDING_RULE


def test_a_call_can_ask_for_a_different_model_than_the_agents():
    from src.agent.nodes import _llm
    assert _llm("some-other-model").model_name == "some-other-model"
    import os
    assert _llm().model_name == os.environ["OPENAI_MODEL"]


def test_a_call_can_ask_for_a_different_model_than_the_agents():
    import os
    from src.agent.nodes import _llm
    assert _llm("some-other-model").model_name == "some-other-model"
    assert _llm().model_name == os.environ["OPENAI_MODEL"]


def test_a_call_can_ask_for_a_different_model_than_the_agents():
    import os
    from src.agent.nodes import _llm
    assert _llm("some-other-model").model_name == "some-other-model"
    assert _llm().model_name == os.environ["OPENAI_MODEL"]
