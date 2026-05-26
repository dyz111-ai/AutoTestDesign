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
