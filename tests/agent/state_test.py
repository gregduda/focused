"""Tests for the agent state models. Run with:  pytest tests/agent"""
from datetime import date
from decimal import Decimal

import pytest
from langchain_core.documents import Document
from pydantic import ValidationError

from src.agent.state import AgentDecision, AgentResult, AgentState, RetrievedChunk
from src.data.models import Action, AgentRequest


def test_decision_needs_only_decision_rationale_and_message():
    d = AgentDecision(decision="DENY", rationale="Past the window.", customer_message="Sorry, ...")
    assert d.refund_amount is None and d.cited_doc_ids == [] and d.stated_condition == "not_stated"


def test_decision_rejects_unknown_labels():
    with pytest.raises(ValidationError):
        AgentDecision(decision="MAYBE", rationale="x", customer_message="x")
    with pytest.raises(ValidationError):
        AgentDecision(decision="DENY", reason_code="BORED", rationale="x", customer_message="x")


def test_result_carries_actions_and_round_trips_through_json():
    r = AgentResult(
        decision="APPROVE", reason_code="CHANGED_MIND", refund_amount="189.05", refund_method="original",
        cited_doc_ids=["ST-CA", "CAT-02"], rationale="10% restocking in CA.", customer_message="Approved.",
        actions=[Action(type="create_rma", order_id="JP-1002", refund_amount=Decimal("189.05"))],
    )
    assert AgentResult.model_validate_json(r.model_dump_json()) == r
    assert r.refund_decimal == Decimal("189.05")


def test_chunk_from_retriever_document():
    doc = Document(page_content="Title (X-1)\n## Section\ntext",
                   metadata={"doc_id": "X-1", "section": "Section", "status": "active",
                             "authority": "authoritative", "distance": 0.25})
    c = RetrievedChunk.from_document(doc)
    assert (c.doc_id, c.distance) == ("X-1", 0.25)


def test_state_is_a_plain_dict_with_the_request():
    state: AgentState = {"request": AgentRequest(order_id="JP-1001", message="hi", today=date(2026, 9, 29))}
    assert state["request"].order_id == "JP-1001"
