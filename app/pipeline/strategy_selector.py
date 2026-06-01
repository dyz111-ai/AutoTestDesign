from app.core.llm_utils import chat_completion_json

VALID_METHODS = [
    "Equivalence Partitioning",
    "Boundary Value Analysis",
    "Decision Table",
    "State Transition Testing",
]

STATE_TRANSITION = "State Transition Testing"


def _is_whitebox_item(item: dict) -> bool:
    if item.get("source") == "whitebox":
        return True
    return str(item.get("coverage_id", "")).upper().startswith("WB-")


def _normalize_method(method: str) -> str:
    normalized = method.strip()
    for valid in VALID_METHODS:
        if valid.lower() == normalized.lower():
            return valid
    return "Equivalence Partitioning"


def _enrich_strategy_entry(item: dict, method: str) -> dict:
    entry = {
        "coverage_id": item["coverage_id"],
        "coverage_item": item["coverage_item"],
        "related_req": item["related_req"],
        "test_method": _normalize_method(method),
    }
    for key in (
        "source", "whitebox_path", "whitebox_events",
        "whitebox_from", "whitebox_to", "whitebox_event", "whitebox_guard",
    ):
        if key in item:
            entry[key] = item[key]
    return entry


def select_strategies(coverage_items: list) -> list:
    """
    Assigns a black-box test technique to each coverage item.
    White-box items are automatically assigned State Transition Testing.
    """
    whitebox_results = []
    blackbox_items = []

    for item in coverage_items:
        if _is_whitebox_item(item):
            whitebox_results.append(_enrich_strategy_entry(item, STATE_TRANSITION))
        else:
            blackbox_items.append(item)

    if not blackbox_items:
        return whitebox_results

    methods_list = "\n".join(f"- {m}" for m in VALID_METHODS)

    prompt = f"""
    You are a Senior QA Test Strategist.

    For each coverage item below, select the most appropriate black-box
    test technique from this list ONLY:

    {methods_list}

    Selection guidelines:
    - Equivalence Partitioning: invalid/valid input classes, empty fields, format errors
    - Boundary Value Analysis: min/max length, limits, thresholds (e.g. password length 7 vs 8)
    - Decision Table: combinations of conditions (e.g. correct email + wrong password)
    - State Transition Testing: state changes over time (e.g. account lock after N failures)

    Use at least 3 different techniques across the full set when possible.

    Return STRICT JSON format — one object per coverage item:

    [
      {{
        "coverage_id": "CI-01",
        "coverage_item": "Email is empty",
        "related_req": "REQ-1",
        "test_method": "Equivalence Partitioning"
      }}
    ]

    Coverage Items:
    {blackbox_items}
    """

    llm_results = chat_completion_json(prompt)
    blackbox_results = [
        _enrich_strategy_entry(item, item["test_method"])
        for item in llm_results
    ]

    by_id = {r["coverage_id"]: r for r in whitebox_results + blackbox_results}
    return [by_id[item["coverage_id"]] for item in coverage_items if item["coverage_id"] in by_id]
