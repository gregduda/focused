"""The nodes of the agent graph. Each takes the state and returns only the keys it changes.

The run goes through these nodes (wiring is in graph.py):

    load_order -> retrieve -> agent <-> tools -> decide -> record_approval   -> END
         |                                             \\-> record_escalation -> END
         |                                              \\-> record_denial ---> END
         \\-> order_not_found -> END (if the order id is unknown)

The "tools" node is not defined here: it is LangGraph's built-in ToolNode, which runs the calculators the agent
asked for. Nodes that need the order database get it from the graph config (see graph.run_agent).
"""
import os
from decimal import Decimal, InvalidOperation

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from src.agent.prompts import DECIDE_INSTRUCTION, build_prefix
from src.agent.state import AgentDecision, AgentState, RetrievedChunk
from src.data.models import Action
from src.data.order_database import OrderDatabase
from src.rag.chunk_retriever import retrieve
from src.tools.calculators import CALCULATOR_TOOLS

NOT_FOUND_MESSAGE = (
    "Thanks for reaching out. I wasn't able to find that order in our system, so I've passed your request to a "
    "specialist who will follow up with you."
)


def _llm() -> ChatOpenAI:
    """A chat model client. The model name comes from OPENAI_MODEL in .env, never hard-coded."""
    return ChatOpenAI(model=os.environ["OPENAI_MODEL"])


def _order_db(config: RunnableConfig) -> OrderDatabase:
    """The read-only order database for this run, passed in through the graph config."""
    return config["configurable"]["order_db"]


def _amount(text: str | None) -> Decimal | None:
    try:
        return None if text is None else Decimal(text)
    except InvalidOperation:
        return None  # an unreadable amount is left empty; the evals flag it


def load_order(state: AgentState, config: RunnableConfig) -> dict:
    """Node 1. Look up the order and its customer in the order database.

    Reads:  state["request"].order_id
    Writes: "order" and "customer". Both are None if the order id does not exist.
    Next:   retrieve if the order was found, otherwise order_not_found (conditional edge in graph.py).
    Plain database lookup; no LLM involved.
    """
    order_db = _order_db(config)
    order = order_db.get_order(state["request"].order_id)
    customer = order_db.get_customer(order.customer_id) if order else None
    return {"order": order, "customer": customer}


def order_not_found(state: AgentState) -> dict:
    """Dead-end branch. The order id was not found, so escalate to a human without calling the LLM (D-024).

    Reads:  state["request"].order_id
    Writes: "decision", a complete ESCALATE decision with escalation_type "order_not_found" and a fixed customer
            message, and "actions" (one open_escalation action). The end state has the same shape as a normal
            run, so the evals treat it like any other escalation.
    Next:   END. Nothing else runs (no retrieval, no LLM).
    """
    order_id = state["request"].order_id
    decision = AgentDecision(
        decision="ESCALATE", escalation_type="order_not_found",
        rationale="The order id was not found in the order system.",
        customer_message=NOT_FOUND_MESSAGE)
    action = Action(type="open_escalation", order_id=order_id, escalation_type="order_not_found",
                    reason="No order with this id exists.", docs_consulted=[])
    return {"decision": decision, "actions": [action]}


def retrieve_policy(state: AgentState) -> dict:
    """Node 2. Fetch the policy chunks the agent will reason from (the RAG step).

    Reads:  state["request"].message
    Writes: "chunks", the top-k retrieved policy chunks, best match first. Each keeps its doc id, section,
            status, authority, and distance so traces and evals can inspect them.
    Next:   agent.
    The model never sees status or authority (see prompts.py). No LLM involved. The search itself is traced
    as its own step in LangSmith (the decorator is on retrieve in chunk_retriever.py).
    """
    # Version 1: the query is the customer's message alone, with no metadata filtering.
    docs = retrieve(state["request"].message)
    return {"chunks": [RetrievedChunk.from_document(d) for d in docs]}


def agent(state: AgentState) -> dict:
    """Node 3. The reasoning step: the LLM reads everything and gathers facts with the calculators.

    Reads:  the request, order, customer, and chunks (turned into the prompt by build_prefix), plus
            state["messages"], the running conversation of earlier model replies and calculator results.
    Writes: appends one model reply to "messages". The reply is either calculator calls (the graph runs them
            in the tools node and comes back here, so this node runs once per round of tool use), or a short
            written analysis with no tool calls, which means the model has what it needs.
    Next:   tools if the reply contains calculator calls, otherwise decide (conditional edge in graph.py).
    The prompt is rebuilt from the state on every call; only the model and tool messages are kept in
    state["messages"].
    """
    messages = build_prefix(state) + state.get("messages", [])
    return {"messages": [_llm().bind_tools(CALCULATOR_TOOLS).invoke(messages)]}


def decide(state: AgentState) -> dict:
    """Node 4. Turn the agent's analysis into the formal, structured decision.

    Makes a second LLM call, constrained to the AgentDecision schema, so the output is always valid: the label
    (APPROVE, DENY, or ESCALATE), reason code, item condition, refund amount, approved action or escalation
    type, cited documents, rationale, and the reply to the customer.
    Reads:  the request, order, customer, chunks, and the full "messages" conversation (including the
            calculator results).
    Writes: "decision".
    Next:   record_approval, record_escalation, or record_denial, depending on the label (route_decision in graph.py).
    """
    messages = build_prefix(state) + state["messages"] + [HumanMessage(DECIDE_INSTRUCTION)]
    return {"decision": _llm().with_structured_output(AgentDecision).invoke(messages)}


def record_approval(state: AgentState) -> dict:
    """Node 5a (APPROVE). Record the action the agent chose, in code.

    Reads:  state["decision"], state["order"].
    Writes: "actions": one Action, the decision's approved_action (create_rma, keep_it_refund, cancel_order,
            create_exchange, create_reshipment, or create_replacement) with the order id, the item id (orders have one item), and the refund amount and
            method from the decision. No money moves; the refund happens after inspection (POL-04).
    If the decision has no approved_action nothing is recorded; the evals catch that mismatch.
    Next:   END.
    """
    d, order = state["decision"], state["order"]
    if not d.approved_action:
        return {"actions": []}
    return {"actions": [Action(
        type=d.approved_action,
        order_id=order.order_id,
        item_id=None if d.approved_action == "cancel_order" else order.items[0].item_id,
        refund_amount=_amount(d.refund_amount),
        refund_method=d.refund_method,
    )]}


def record_escalation(state: AgentState) -> dict:
    """Node 5b (ESCALATE). Hand the case to a human by recording an open_escalation action.

    Reads:  state["decision"], state["order"].
    Writes: "actions": one open_escalation Action, with the decision's escalation type ("standard" if the model
            left it empty), its internal rationale as the reason, and the documents it cited.
    Next:   END.
    """
    d, order = state["decision"], state["order"]
    return {"actions": [Action(
        type="open_escalation", order_id=order.order_id, escalation_type=d.escalation_type or "standard",
        reason=d.rationale, docs_consulted=d.cited_doc_ids)]}


def record_denial(state: AgentState) -> dict:
    """Node 5c (DENY). Note the denial so there is a record of what was decided and why.

    Reads:  state["decision"], state["order"].
    Writes: "actions": one record_denial Action with the decision's rationale as the reason and the documents
            it cited. Nothing else happens in our systems: a clear denial needs no further action (OPS-01).
    Next:   END.
    """
    d, order = state["decision"], state["order"]
    return {"actions": [Action(
        type="record_denial", order_id=order.order_id, reason=d.rationale, docs_consulted=d.cited_doc_ids)]}
