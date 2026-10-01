"""The two versions of the agent, as named sets of settings (D-091).

v1 is the original: the search runs on the customer's message alone, with no filtering, and nothing else is added.
v2 is what the improvements of D-067 to D-089 add up to. Each setting can still be switched on or off on its own (the
ablations were run that way): `run_agent(request, escalation_check=False)`, or `run_eval --without escalation_check`.

  retrieval           "v1" search only; "core_order" adds the core policy documents and the documents the order's
                      category, state, season, and tiers point to (src/rag/forced_docs.py)
  authoritative_only  the search skips stale and non-authoritative documents (D-071)
  scope_to_order      the search skips other categories' documents and other states' addenda (D-072)
  grounding_rule      a behavior rule in the prompt: no guessing values, no escalating just to ask for details (D-072,
                      D-087)
  amount_guard        an approved refund must be a calculator result; no refund amount on a denial or escalation (D-074,
                      D-080)
  escalation_check    a separate model call asks whether any escalation rule applies; it can use its own model,
                      OPENAI_ESCALATION_CHECK_MODEL (D-080, D-089)
"""
V1 = {
    "retrieval": "v1", "authoritative_only": False, "scope_to_order": False, "grounding_rule": False,
    "amount_guard": False, "escalation_check": False,
}
V2 = {
    "retrieval": "core_order", "authoritative_only": True, "scope_to_order": True, "grounding_rule": True,
    "amount_guard": True, "escalation_check": True,
}
VERSIONS = {"v1": V1, "v2": V2}


def options_for(version: str = "v2", **overrides) -> dict:
    """The settings of a version, with any of them overridden by name."""
    if version not in VERSIONS:
        raise ValueError(f"unknown version {version!r}; expected one of {sorted(VERSIONS)}")
    unknown = set(overrides) - set(V1)
    if unknown:
        raise ValueError(f"unknown setting(s) {sorted(unknown)}; the settings are {sorted(V1)}")
    return {**VERSIONS[version], **overrides}
