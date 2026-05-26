from app.core.llm_utils import chat_completion_json


def _priority_from_score(risk_score: int) -> str:
    if risk_score >= 7:
        return "High"
    if risk_score >= 4:
        return "Medium"
    return "Low"


def analyze_risks(requirements: list) -> list:
    """
    Analyzes risk and priority for each structured requirement.
    Returns list with requirement_id, risk_score, priority, and reason.
    """

    prompt = f"""
    You are a Senior QA Risk Analyst.

    For each requirement below, assess testing risk and priority.

    Scoring rules:
    - risk_score: integer from 1 (lowest risk) to 10 (highest risk)
    - priority must align with risk_score:
      - High: risk_score 7-10 (core features, security, data integrity)
      - Medium: risk_score 4-6 (usability, validation, non-critical flows)
      - Low: risk_score 1-3 (minor or cosmetic behavior)

    Consider business impact, security, compliance, and user-facing criticality.

    Return STRICT JSON format like this:

    [
      {{
        "requirement_id": "REQ-1",
        "risk_score": 9,
        "priority": "High",
        "reason": "Login is a core function"
      }}
    ]

    Requirements:
    {requirements}
    """

    risk_results = chat_completion_json(prompt)

    normalized = []
    for item in risk_results:
        score = int(item["risk_score"])
        score = max(1, min(10, score))
        normalized.append({
            "requirement_id": item["requirement_id"],
            "risk_score": score,
            "priority": _priority_from_score(score),
            "reason": item["reason"],
        })

    return normalized
