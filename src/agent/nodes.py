"""The nodes of the agent graph. Each takes the state and returns only the keys it changes.

The run goes through these nodes (wiring is in graph.py):

    load_order -> retrieve -> agent <-> tools -> decide -> record_approval   -> END
         |                                             \\-> record_escalation -> END
         |                                              \\-> record_denial ---> END
         \\-> order_not_found -> END (if the order id is unknown)

The "tools" node is not defined here: it is LangGraph's built-in ToolNode, which runs the calculators the agent
asked for. Nodes that need the order database get it from the graph config (see graph.run_agent).
"""
import json
import os
from decimal import Decimal, InvalidOperation

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from src.agent.prompts import (
    DECIDE_INSTRUCTION, build_escalation_check_input, build_prefix, escalation_finding_message,
)
from src.agent.state import AgentDecision, AgentState, EscalationCheck, RetrievedChunk
from src.data.models import Action
from src.data.order_database import OrderDatabase
from src.rag.chunk_retriever import docs_by_id, retrieve
from src.rag.forced_docs import forced_doc_ids
from src.tools.calculators import CALCULATOR_TOOLS

NOT_FOUND_MESSAGE = (
    "Thanks for reaching out. I wasn't able to find that order in our system, so I've passed your request to a "
    "specialist who will follow up with you."
)


def _llm(model: str | None = None) -> ChatOpenAI:
    """A chat model client. The model name comes from OPENAI_MODEL in .env, never hard-coded, unless a call asks for
    another one (the escalation check can, see OPENAI_ESCALATION_CHECK_MODEL)."""
    # A call that has not answered in 90 seconds is retried (twice) instead of waiting out the client's 10-minute
    # default: a dead connection once froze an experiment for an hour (D-081).
    return ChatOpenAI(model=model or os.environ["OPENAI_MODEL"], timeout=90, max_retries=2)


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


def retrieve_policy(state: AgentState, config: RunnableConfig) -> dict:
    """Node 2. Fetch the policy chunks the agent will reason from (the RAG step).

    Reads:  state["request"].message, and for the experimental modes the order and customer.
    Writes: "chunks": the top-k search results, best match first, then (modes core and core_order only) every chunk of
            the documents added by rule (forced_docs.py), skipping chunks the search already returned. Each keeps its
            doc id, section, status, authority, and distance so traces and evals can inspect them.
    Next:   agent.
    The model never sees status or authority (see prompts.py). No LLM involved. The search itself is traced
    as its own step in LangSmith (the decorator is on retrieve in chunk_retriever.py).
    """
    # The default, version 1: the query is the customer's message alone, with no metadata filtering.
    opts = config["configurable"]
    scope = {"category": state["order"].items[0].category, "state": state["order"].ship_to_state} \
        if opts.get("scope_to_order") else {}
    docs = retrieve(state["request"].message, authoritative_only=opts.get("authoritative_only", False), **scope)
    mode = config["configurable"].get("retrieval", "v1")
    forced = forced_doc_ids(mode, state["order"], state["customer"])
    if forced:
        seen = {(d.metadata["doc_id"], d.metadata["section"]) for d in docs}
        docs += [d for d in docs_by_id(forced) if (d.metadata["doc_id"], d.metadata["section"]) not in seen]
    return {"chunks": [RetrievedChunk.from_document(d) for d in docs]}


def agent(state: AgentState, config: RunnableConfig) -> dict:
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
    messages = build_prefix(state, config["configurable"].get("grounding_rule", False)) + state.get("messages", [])
    return {"messages": [_llm().bind_tools(CALCULATOR_TOOLS).invoke(messages)]}


def escalation_check(state: AgentState, config: RunnableConfig) -> dict:
    """Node 3b (optional, D-080). A separate, narrow model call that asks only: does any escalation rule in the excerpts
    apply to this case? Off by default, when this node does nothing.

    Reads:  the request, order, customer, chunks, and the calculator results in "messages".
    Writes: when a rule applies, one message that tells the decision step to record ESCALATE (and a note in "guards");
            otherwise nothing.
    Next:   decide.
    """
    if not config["configurable"].get("escalation_check", False):
        return {}
    # OPENAI_ESCALATION_CHECK_MODEL lets a stronger model do this one narrow call while the agent runs on a cheaper one (D-089).
    check_model = os.environ.get("OPENAI_ESCALATION_CHECK_MODEL") or None
    check = _llm(check_model).with_structured_output(EscalationCheck).invoke(build_escalation_check_input(state))
    if not check.escalate:
        return {"guards": ["escalation check: no rule applies"]}
    return {"messages": [HumanMessage(escalation_finding_message(check.rule_id, check.escalation_type, check.reason))],
            "guards": [f"escalation check: {check.rule_id} applies: {check.reason}"]}


def decide(state: AgentState, config: RunnableConfig) -> dict:
    """Node 4. Turn the agent's analysis into the formal, structured decision.

    Makes a second LLM call, constrained to the AgentDecision schema, so the output is always valid: the label
    (APPROVE, DENY, or ESCALATE), reason code, item condition, refund amount, approved action or escalation
    type, cited documents, rationale, and the reply to the customer.
    Reads:  the request, order, customer, chunks, and the full "messages" conversation (including the
            calculator results).
    Writes: "decision".
    Next:   record_approval, record_escalation, or record_denial, depending on the label (route_decision in graph.py).
    """
    messages = build_prefix(state, config["configurable"].get("grounding_rule", False)) + state["messages"] \
        + [HumanMessage(DECIDE_INSTRUCTION)]
    decision = _llm().with_structured_output(AgentDecision).invoke(messages)
    notes = []
    if decision.decision != "ESCALATE" and any(isinstance(g, str) and g.startswith("escalation check: ") and "no rule applies" not in g
                                              for g in state.get("guards", [])):
        notes.append("the decision ignored the escalation check")
    if not config["configurable"].get("amount_guard", False):
        return {"decision": decision, "guards": notes}
    decision, note = correct_refund(decision, state["messages"])
    return {"decision": decision, "guards": notes + ([note] if note else [])}


def correct_refund(decision: AgentDecision, messages: list) -> tuple[AgentDecision, str | None]:
    """The amount guard (D-074, D-080): a refund amount belongs only to an approval, and must be a figure the refund
    calculator produced.

    On a DENY or ESCALATE the amount is cleared (no money moves, and an amount left in the field contradicts the
    decision). On an APPROVE, if the model's refund_amount is not the total of any compute_refund result in this run,
    it was copied wrongly or made up, so it is replaced with the total of the last compute_refund call. Each
    correction is returned as a note. Left alone: an empty amount, an APPROVE in a run with no compute_refund call,
    and an amount that equals some calculator total (the model may legitimately settle on an earlier scenario)."""
    totals = []
    for m in messages:
        if getattr(m, "name", None) == "compute_refund" and getattr(m, "status", "success") != "error":
            try:
                totals.append(Decimal(json.loads(m.content)["total_to_customer"]))
            except (ValueError, KeyError, TypeError, InvalidOperation):
                continue  # an unreadable result is not a figure to trust
    stated = _amount(decision.refund_amount)
    if stated is not None and decision.decision != "APPROVE":
        return (decision.model_copy(update={"refund_amount": None}),
                f"refund {stated} cleared: a {decision.decision} carries no refund")
    if decision.decision != "APPROVE" or stated is None or not totals or stated in totals:
        return decision, None
    fixed = totals[-1]
    note = f"refund {stated} was not a calculator result; replaced with the last compute_refund total {fixed}"
    return decision.model_copy(update={"refund_amount": str(fixed)}), note


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
