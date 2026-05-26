import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm_client import DEFAULT_MODEL, client

response = client.chat.completions.create(
    model=DEFAULT_MODEL,
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "你好!"},
    ],
    stream=False,
)

print(response.choices[0].message.content)
