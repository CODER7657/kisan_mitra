"""Which providers are available, read from the environment.

Groq is used when GROQ_API_KEY is set, OpenAI when only OPENAI_API_KEY is. Groq has
no vision model on this key, so with Groq the photo is read by the local classifier
only; with OpenAI the photo is also sent to GPT-4o.
"""

import os
from dataclasses import dataclass

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class Provider:
    name: str  # "groq" or "openai"
    api_key: str
    base_url: str | None
    chat_model: str
    asr_model: str
    sees_images: bool


def provider() -> Provider | None:
    groq = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    choice = os.getenv("LLM_PROVIDER", "").strip().lower()
    if groq and choice != "openai":
        return Provider("groq", groq, GROQ_BASE_URL,
                        os.getenv("GROQ_CHAT_MODEL", "qwen/qwen3.8-27b"),
                        os.getenv("GROQ_ASR_MODEL", "whisper-large-v3"), sees_images=False)
    if openai_key:
        return Provider("openai", openai_key, None, os.getenv("OPENAI_CHAT_MODEL", "gpt-4o"),
                        "whisper-1", sees_images=True)
    return None


def client(p: Provider):
    from openai import OpenAI

    return OpenAI(api_key=p.api_key, base_url=p.base_url, timeout=60, max_retries=2)
