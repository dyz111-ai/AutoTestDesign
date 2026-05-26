from app.core.llm_utils import chat_completion_json


def extract_requirements(prd_text: str):
    """
    Uses LLM to extract structured requirements from PRD
    """

    prompt = f"""
    You are a Senior QA Analyst.

    Extract all testable requirements from the PRD.

    Return STRICT JSON format like this:

    [
      {{
        "requirement_id": "REQ-1",
        "description": "",
        "type": "functional"
      }}
    ]

    PRD:
    {prd_text}
    """

    return chat_completion_json(prompt)
