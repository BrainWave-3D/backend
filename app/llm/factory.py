from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.providers import GeminiProvider, GroqProvider, MockProvider


def get_llm_provider() -> LLMProvider:
    provider_name = settings.llm_provider.lower().strip()
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "groq":
        return GroqProvider()
    if provider_name == "gemini":
        return GeminiProvider()
    raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")
