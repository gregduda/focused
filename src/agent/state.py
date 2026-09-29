"""The state that flows through the LangGraph agent, and the structured result it produces.

Flow (see design/agent-run-flow.md):  request -> load order -> retrieve -> LLM + tool loop -> result

Each node reads the state and returns only the keys it changes. The store (database plus in-memory
actions) is not part of the state because it is not serializable; nodes and tools get it from the
graph config instead.
"""
from decimal import Decimal
from typing import Annotated, Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.data.models import Action, AgentRequest, Customer, Order

Decision = Literal["APPROVE", "DENY", "ESCALATE"]

# OPS-05, minus GIFT_UNWANTED (gifts are out of scope, D-023). The first four are "our error" reasons
# (fees waived); the rest are customer-initiated.
ReasonCode = Literal[
    "DEFECTIVE", "DAMAGED_IN_TRANSIT", "WRONG_ITEM_SENT", "NOT_AS_DESCRIBED",
    "CHANGED_MIND", "WRONG_SIZE_FIT", "ORDERED_BY_MISTAKE", "FOUND_CHEAPER", "LATE_DELIVERY",
]

# What the customer says about the item (from the message, never from the database).
StatedCondition = Literal["sealed_unopened", "opened_unused", "assembled", "used_or_worn", "not_stated"]

# Our own labels for why a case went to a human; used to slice eval results (D-006).
EscalationType = Literal[
    "standard", "high_value", "warranty", "loss_prevention", "safety", "goodwill", "missing_package",
    "needs_info", "order_not_found",
]


class RetrievedChunk(BaseModel):
    """One policy chunk returned by the retriever, kept small and flat so traces and evals can read it."""
    doc_id: str
    section: str
    status: str
    authority: str
    distance: float
    text: str

    @classmethod
    def from_document(cls, doc: Document) -> "RetrievedChunk":
        m = doc.metadata
        return cls(doc_id=m["doc_id"], section=m["section"], status=m["status"], authority=m["authority"],
                   distance=m["distance"], text=doc.page_content)


class AgentDecision(BaseModel):
    """What the LLM must fill in at the end of a run. This is the schema given to the model."""
    decision: Decision
    reason_code: ReasonCode | None = Field(
        default=None, description="The customer's reason for the request, as stated. Null if not a return or refund.")
    stated_condition: StatedCondition = Field(
        default="not_stated", description="The item's condition as the customer describes it in the message.")
    # A string, not Decimal: pydantic's Decimal schema has a regex that made gpt-5.4-nano run away
    # (D-029), and the calculators return strings like "189.05" that the model only has to copy.
    refund_amount: str | None = Field(
        default=None,
        description="Total refund in dollars as a two-decimal string, copied exactly from a calculator "
                    "result, e.g. \"189.05\". Null unless the amount is known.")
    refund_method: Literal["original", "store_credit"] | None = None
    escalation_type: EscalationType | None = Field(
        default=None, description="Required when the decision is ESCALATE; otherwise null.")
    cited_doc_ids: list[str] = Field(
        default_factory=list, description="IDs of the policy documents the decision relied on, e.g. CAT-02.")
    rationale: str = Field(
        description="Short internal explanation of how the policy rules were applied. Not shown to the customer.")
    customer_message: str = Field(description="The reply to the customer.")

    @property
    def refund_decimal(self) -> Decimal | None:
        """The refund as a Decimal for comparisons in code and evals."""
        return None if self.refund_amount is None else Decimal(self.refund_amount)


class AgentResult(AgentDecision):
    """The final structured output: the LLM's decision plus what the code recorded."""
    actions: list[Action] = Field(default_factory=list)  # copied from the store when the run ends


class AgentState(TypedDict, total=False):
    request: AgentRequest                                # input, set once
    order: Order | None                                  # set by the load node; None if the id is unknown
    customer: Customer | None
    chunks: list[RetrievedChunk]                         # set by the retrieve node
    messages: Annotated[list[AnyMessage], add_messages]  # the LLM and tool conversation
    result: AgentResult | None                           # set by the final node
