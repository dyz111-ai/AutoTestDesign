from app.core.llm_utils import chat_completion_json

VALID_METHODS = [
    "Equivalence Partitioning",
    "Boundary Value Analysis",
    "Decision Table",
    "State Transition Testing",
]


def _normalize_method(method: str) -> str:
    normalized = method.strip()
    for valid in VALID_METHODS:
        if valid.lower() == normalized.lower():
            return valid
    return "Equivalence Partitioning"


def select_strategies(coverage_items: list) -> list:
    """
    Assigns a black-box test technique to each coverage item.
    """

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
    {coverage_items}
    """

    results = chat_completion_json(prompt)

    enriched = []
    for item in results:
        enriched.append({
            "coverage_id": item["coverage_id"],
            "coverage_item": item["coverage_item"],
            "related_req": item["related_req"],
            "test_method": _normalize_method(item["test_method"]),
        })

    return enriched
