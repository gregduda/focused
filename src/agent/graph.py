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
    agent, decide, load_order, order_not_found, record_approval, record_denial, record_escalation,
    retrieve_policy,
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
    """Calculator calls go to the tools node; a reply without tool calls means the agent is done gathering."""
    return "tools" if state["messages"][-1].tool_calls else "decide"


def route_decision(state: AgentState) -> str:
    """The routing on the decision the model made."""
    return {"APPROVE": "record_approval", "ESCALATE": "record_escalation", "DENY": "record_denial"}[
        state["decision"].decision]


def build_graph() -> CompiledStateGraph:
    g = StateGraph(AgentState)
    g.add_node("load_order", load_order)
    g.add_node("order_not_found", order_not_found)
    g.add_node("retrieve", retrieve_policy)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(CALCULATOR_TOOLS))
    g.add_node("decide", decide)
    g.add_node("record_approval", record_approval)
    g.add_node("record_escalation", record_escalation)
    g.add_node("record_denial", record_denial)

    g.add_edge(START, "load_order")
    g.add_conditional_edges("load_order", route_after_load, ["retrieve", "order_not_found"])
    g.add_edge("order_not_found", END)
    g.add_edge("retrieve", "agent")
    g.add_conditional_edges("agent", route_after_agent, ["tools", "decide"])
    g.add_edge("tools", "agent")
    g.add_conditional_edges("decide", route_decision, ["record_approval", "record_escalation", "record_denial"])
    g.add_edge("record_approval", END)
    g.add_edge("record_escalation", END)
    g.add_edge("record_denial", END)
    return g.compile()


def run_agent(request: AgentRequest, order_db: OrderDatabase | None = None) -> AgentResult:
    """Run the agent once and return its result: the decision plus the actions the record nodes added."""
    out = build_graph().invoke(
        {"request": request},
        config={
            "configurable": {"order_db": order_db or OrderDatabase()},
            "recursion_limit": MAX_STEPS,
            "run_name": "refund_agent",
            "metadata": {"order_id": request.order_id, "today": request.today.isoformat()},
        },
    )
    return AgentResult(**out["decision"].model_dump(), actions=out.get("actions", []), retrieved=out.get("chunks", []))
