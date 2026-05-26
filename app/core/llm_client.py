import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=DEEPSEEK_BASE_URL,
)
