from app.core.llm_utils import chat_completion_json


def generate_coverage_items(requirements: list) -> list:
    """
    Identifies testable coverage items from structured requirements.
    Returns coverage_id, coverage_item description, and related_req.
    """

    prompt = f"""
    You are a Senior QA Test Designer.

    For each requirement below, identify concrete coverage items — specific
    conditions or scenarios that must be tested (valid paths, invalid inputs,
    boundaries, state changes, combinations).

    Rules:
    - Generate at least 1 coverage item per requirement; typically 2-4 per requirement.
    - Use sequential coverage IDs: CI-01, CI-02, CI-03, ...
    - Each coverage item must map to exactly one related_req (requirement_id).
    - Write coverage_item as a short, testable condition (e.g. "Email is empty").

    Return STRICT JSON format like this:

    [
      {{
        "coverage_id": "CI-01",
        "coverage_item": "Email is empty",
        "related_req": "REQ-1"
      }}
    ]

    Requirements:
    {requirements}
    """

    return chat_completion_json(prompt)
