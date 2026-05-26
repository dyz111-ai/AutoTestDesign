from app.core.llm_utils import chat_completion_json


def generate_testcases(
    requirements: list,
    risk_results: list,
    coverage_with_strategy: list,
) -> list:
    """
    Generates one structured test case per coverage item, using requirement,
    risk priority, coverage item, and assigned test strategy.
    """

    prompt = f"""
    You are a Senior QA Test Case Author.

    Generate exactly ONE detailed test case for EACH coverage item below.
    Use the related requirement context, risk priority, coverage condition,
    and assigned test_method to design the test.

    Requirements context:
    {requirements}

    Risk analysis:
    {risk_results}

    Coverage items with test strategies:
    {coverage_with_strategy}

    For each item, set priority from the risk analysis of its related_req.

    Return STRICT JSON format — a flat array, one test case per coverage item:

    [
      {{
        "tc_id": "TC-01",
        "req_id": "REQ-1",
        "coverage_id": "CI-01",
        "test_method": "Equivalence Partitioning",
        "priority": "High",
        "preconditions": "User is on the login page",
        "test_data": "email=, password=ValidPass123",
        "steps": ["Navigate to login page", "Leave email empty", "Enter password", "Click Login"],
        "expected_result": "System displays email required error message"
      }}
    ]

    Rules:
    - tc_id must be sequential: TC-01, TC-02, ...
    - test_method must match the assigned test_method for that coverage_id
    - priority must be High, Medium, or Low from risk analysis
    - steps must be a JSON array of strings
    """

    return chat_completion_json(prompt)
