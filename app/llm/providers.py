from __future__ import annotations

import asyncio
from typing import AsyncIterator

from app.core.config import settings
from app.llm.base import ChatCompletionRequest, ChatProviderChunk


class MockProvider:
    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[ChatProviderChunk]:
        user_prompt = request.messages[-1].content if request.messages else ""
        text = (
            "I am running in mock mode right now. "
            "You said: "
            f"{user_prompt[:500]}"
        )
        for token in text.split(" "):
            await asyncio.sleep(0)
            yield ChatProviderChunk(text=f"{token} ", done=False)
        yield ChatProviderChunk(text="", done=True)


class GeminiProvider:
    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for provider 'gemini'")

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[ChatProviderChunk]:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # type: ignore[import-not-found]
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError(
                "Missing LangChain Gemini dependencies. Install langchain-google-genai."
            ) from exc

        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model_name,
            google_api_key=settings.llm_api_key,
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        messages = [SystemMessage(content=request.system_prompt)]
        for msg in request.messages:
            if msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
            else:
                messages.append(HumanMessage(content=msg.content))

        async for chunk in llm.astream(messages):
            content = getattr(chunk, "content", None)
            if content:
                yield ChatProviderChunk(text=str(content), done=False)

        yield ChatProviderChunk(text="", done=True)


class GroqProvider:
    def __init__(self) -> None:
        if not (settings.groq_api_key or settings.llm_api_key):
            raise RuntimeError("GROQ_API_KEY (or LLM_API_KEY) is required for provider 'groq'")

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[ChatProviderChunk]:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # type: ignore[import-not-found]
            from langchain_groq import ChatGroq  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("Missing LangChain Groq dependencies. Install langchain-groq.") from exc

        llm = ChatGroq(
            model=settings.llm_model_name,
            api_key=settings.groq_api_key or settings.llm_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        messages = [SystemMessage(content=request.system_prompt)]
        for msg in request.messages:
            if msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
            else:
                messages.append(HumanMessage(content=msg.content))

        async for chunk in llm.astream(messages):
            content = getattr(chunk, "content", None)
            if content:
                yield ChatProviderChunk(text=str(content), done=False)

        yield ChatProviderChunk(text="", done=True)
