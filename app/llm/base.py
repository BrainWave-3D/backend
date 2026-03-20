from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class ChatMessageInput:
    role: str
    content: str


@dataclass
class ChatCompletionRequest:
    system_prompt: str
    messages: list[ChatMessageInput]
    temperature: float
    max_tokens: int


@dataclass
class ChatProviderChunk:
    text: str
    done: bool = False


class LLMProvider(Protocol):
    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[ChatProviderChunk]:
        ...
