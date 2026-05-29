import json

from app.core.llm_client import DEFAULT_MODEL, client


def parse_llm_json(raw_output: str):
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "")
        cleaned = cleaned.replace("```", "")
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def chat_completion_json(prompt: str) -> list | dict:
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return parse_llm_json(response.choices[0].message.content)


def chat_completion_text(prompt: str) -> str:
    """Send a prompt and return the raw text response (no JSON parsing)."""
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    content = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        # Remove opening fence: ```python or just ```
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1:]
        # Remove closing fence
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    return content
