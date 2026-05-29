from app.core.llm_utils import chat_completion_json


def generate_oracle(requirement: dict, test_data: str) -> dict:
    """
    Synthesizes a Test Oracle (expected result + validation rules) for a
    given requirement and specific test data input.
    """

    prompt = f"""
    You are a Senior QA Test Oracle Specialist.

    Given the software requirement below and a specific set of test data,
    synthesize the precise expected result and validation rules that a tester
    should verify.

    Requirement:
    - ID: {requirement.get("requirement_id", "N/A")}
    - Description: {requirement.get("description", "N/A")}
    - Type: {requirement.get("type", "functional")}

    Test Data / Input Scenario:
    {test_data}

    Return STRICT JSON with this exact structure:

    {{
      "requirement_id": "{requirement.get("requirement_id", "N/A")}",
      "test_data": "{test_data}",
      "expected_output": "Precise description of what the system must produce or display",
      "validation_rules": [
        "Rule 1: specific, measurable condition to check",
        "Rule 2: another condition",
        "Rule 3: edge / boundary condition if applicable"
      ],
      "oracle_type": "one of: Specified Output / Heuristic / Consistency / Exception",
      "rationale": "Brief explanation of WHY this is the expected result based on the requirement"
    }}

    Rules:
    - expected_output must be specific and verifiable, not vague.
    - validation_rules must be concrete checks (status codes, messages, state changes).
    - oracle_type classifies the kind of oracle used.
    - rationale links back to the requirement text.
    """

    return chat_completion_json(prompt)


def batch_generate_oracles(requirements: list, testcases: list) -> list:
    """
    Enriches existing test cases with oracle details by matching requirement context.
    Returns list of oracle records.
    """

    req_map = {r["requirement_id"]: r for r in requirements}
    oracles = []

    for tc in testcases:
        req_id = tc.get("req_id", "")
        req = req_map.get(req_id, {"requirement_id": req_id, "description": "", "type": "functional"})
        test_data = tc.get("test_data", "")

        result = generate_oracle(req, test_data)
        result["tc_id"] = tc.get("tc_id", "")
        result["coverage_id"] = tc.get("coverage_id", "")
        oracles.append(result)

    return oracles
