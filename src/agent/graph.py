"""The agent graph (see design/agent-run-flow.md).

    START -> load_order --(order missing)--> order_not_found -> END
                        \\--(found)--> retrieve -> agent <-> tools
                                                   agent --(no more tool calls)--> decide
              decide --(APPROVE)--> record_approval ---> END
                     \\--(ESCALATE)--> record_escalation --> END
                     \\--(DENY)--> record_denial ---------> END
"""
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from src.agent.nodes import (
    agent, decide, escalation_check, load_order, order_not_found, record_approval, record_denial,
    record_escalation, retrieve_policy,
)
from src.agent.state import AgentResult, AgentState
from src.tools.calculators import CALCULATOR_TOOLS
from src.data.models import AgentRequest
from src.data.order_database import OrderDatabase

load_dotenv()

MAX_STEPS = 20  # guards against a runaway tool loop


def route_after_load(state: AgentState) -> str:
    return "retrieve" if state["order"] else "order_not_found"


def route_after_agent(state: AgentState) -> str:
    """Calculator calls go to the tools node; a reply without tool calls means the agent is done gathering, and the
    escalation check (a no-op unless switched on) runs before the decision."""
    return "tools" if state["messages"][-1].tool_calls else "escalation_check"


def route_decision(state: AgentState) -> str:
    """The routing on the decision the model made."""
    return {"APPROVE": "record_approval", "ESCALATE": "record_escalation", "DENY": "record_denial"}[
        state["decision"].decision]


def make_tool_node() -> ToolNode:
    """The calculator node. handle_tool_errors=True: a calculator that raises (for example an empty list of windows)
    returns its error message to the model so it can correct the call, as calculators.py promises, instead of
    crashing the whole run."""
    return ToolNode(CALCULATOR_TOOLS, handle_tool_errors=True)


def build_graph() -> CompiledStateGraph:
    g = StateGraph(AgentState)
    g.add_node("load_order", load_order)
    g.add_node("order_not_found", order_not_found)
    g.add_node("retrieve", retrieve_policy)
    g.add_node("agent", agent)
    g.add_node("tools", make_tool_node())
    g.add_node("escalation_check", escalation_check)
    g.add_node("decide", decide)
    g.add_node("record_approval", record_approval)
    g.add_node("record_escalation", record_escalation)
    g.add_node("record_denial", record_denial)

    g.add_edge(START, "load_order")
    g.add_conditional_edges("load_order", route_after_load, ["retrieve", "order_not_found"])
    g.add_edge("order_not_found", END)
    g.add_edge("retrieve", "agent")
    g.add_conditional_edges("agent", route_after_agent, ["tools", "escalation_check"])
    g.add_edge("escalation_check", "decide")
    g.add_edge("tools", "agent")
    g.add_conditional_edges("decide", route_decision, ["record_approval", "record_escalation", "record_denial"])
    g.add_edge("record_approval", END)
    g.add_edge("record_escalation", END)
    g.add_edge("record_denial", END)
    return g.compile()


def run_agent(request: AgentRequest, order_db: OrderDatabase | None = None, retrieval: str = "v1",
              authoritative_only: bool = False, scope_to_order: bool = False, grounding_rule: bool = False,
              amount_guard: bool = False, escalation_check: bool = False) -> AgentResult:
    """Run the agent once and return its result: the decision plus the actions the record nodes added.
    `retrieval` picks the retrieval mode (v1, core, or core_order; see src/rag/forced_docs.py); v1 is the default.
    `authoritative_only` leaves stale and non-authoritative documents out of the search (D-071); off by default.
    `scope_to_order` limits category documents and state addenda in the search to the order's own (D-072); off by default.
    `grounding_rule` adds the grounding rule to the system prompt (D-072); off by default.
    `amount_guard` replaces an approved refund that is not a calculator result with the last calculator total (D-074);
    off by default.
    `escalation_check` adds a separate model call that checks whether any escalation rule applies (D-080); off by
    default."""
    out = build_graph().invoke(
        {"request": request},
        config={
            "configurable": {"order_db": order_db or OrderDatabase(), "retrieval": retrieval,
                             "authoritative_only": authoritative_only, "scope_to_order": scope_to_order,
                             "grounding_rule": grounding_rule, "amount_guard": amount_guard,
                             "escalation_check": escalation_check},
            "recursion_limit": MAX_STEPS,
            "run_name": "refund_agent",
            "metadata": {"order_id": request.order_id, "today": request.today.isoformat(), "retrieval": retrieval,
                         "authoritative_only": authoritative_only, "scope_to_order": scope_to_order,
                         "grounding_rule": grounding_rule, "amount_guard": amount_guard,
                         "escalation_check": escalation_check},
        },
    )
    return AgentResult(**out["decision"].model_dump(), actions=out.get("actions", []), retrieved=out.get("chunks", []),
                       guards=out.get("guards", []))
