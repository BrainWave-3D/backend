from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["system", "user", "assistant"]


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    prediction_summary: str | None = Field(default=None, max_length=4000)


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    user_id: str
    role: ChatRole
    content: str
    provider: str | None = None
    model_name: str | None = None
    created_at: datetime


class ChatConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatConversationCreateResponse(BaseModel):
    conversation: ChatConversationRead


class ChatConversationListResponse(BaseModel):
    items: list[ChatConversationRead]


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageRead]


class ChatSendResponse(BaseModel):
    conversation: ChatConversationRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead


class ChatWSIncoming(BaseModel):
    type: Literal["user_message"] = "user_message"
    content: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None
    prediction_summary: str | None = Field(default=None, max_length=4000)
