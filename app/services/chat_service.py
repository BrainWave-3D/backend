from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db.models import CHAT_CONVERSATIONS_COLLECTION, CHAT_MESSAGES_COLLECTION
from app.llm import ChatCompletionRequest, ChatMessageInput, get_llm_provider


class ChatService:
    async def get_or_create_default_conversation(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
    ) -> dict[str, Any]:
        document = await db[CHAT_CONVERSATIONS_COLLECTION].find_one(
            {"user_id": user_id, "title": "default"},
            sort=[("updated_at", -1)],
        )
        if document is None:
            return await self.create_conversation(db, user_id=user_id, title="default")
        return self._serialize_conversation(document)

    async def create_conversation(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        await db[CHAT_CONVERSATIONS_COLLECTION].insert_one(document)
        return self._serialize_conversation(document)

    async def get_conversation(
        self,
        db: AsyncIOMotorDatabase,
        conversation_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        if not ObjectId.is_valid(conversation_id):
            return None
        document = await db[CHAT_CONVERSATIONS_COLLECTION].find_one(
            {"_id": ObjectId(conversation_id), "user_id": user_id}
        )
        if document is None:
            return None
        return self._serialize_conversation(document)

    async def list_conversations(
        self,
        db: AsyncIOMotorDatabase,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        cursor = (
            db[CHAT_CONVERSATIONS_COLLECTION]
            .find({"user_id": user_id})
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [self._serialize_conversation(doc) for doc in docs]

    async def save_message(
        self,
        db: AsyncIOMotorDatabase,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "provider": provider,
            "model_name": model_name,
            "created_at": now,
        }
        await db[CHAT_MESSAGES_COLLECTION].insert_one(document)
        await db[CHAT_CONVERSATIONS_COLLECTION].update_one(
            {"_id": ObjectId(conversation_id), "user_id": user_id},
            {"$set": {"updated_at": now}},
        )
        return self._serialize_message(document)

    async def list_messages(
        self,
        db: AsyncIOMotorDatabase,
        conversation_id: str,
        user_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        if not ObjectId.is_valid(conversation_id):
            return []
        cursor = (
            db[CHAT_MESSAGES_COLLECTION]
            .find({"conversation_id": conversation_id, "user_id": user_id})
            .sort("created_at", 1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [self._serialize_message(doc) for doc in docs]

    async def build_llm_messages(
        self,
        db: AsyncIOMotorDatabase,
        conversation_id: str,
        user_id: str,
        latest_user_prompt: str,
    ) -> list[ChatMessageInput]:
        history = await self.list_messages(db, conversation_id=conversation_id, user_id=user_id, limit=10)
        messages: list[ChatMessageInput] = []
        for item in history:
            if item["role"] not in {"user", "assistant"}:
                continue
            messages.append(ChatMessageInput(role=item["role"], content=item["content"]))

        if not history or history[-1]["content"] != latest_user_prompt:
            messages.append(ChatMessageInput(role="user", content=latest_user_prompt))
        return messages

    async def stream_assistant_reply(
        self,
        db: AsyncIOMotorDatabase,
        conversation_id: str,
        user: dict[str, Any],
        user_prompt: str,
        prediction_summary: str | None,
    ) -> AsyncIterator[str]:
        context_block = self._build_context_block(user=user, prediction_summary=prediction_summary)
        system_prompt = (
            settings.chat_system_prompt
            + "\n\n"
            + "User context:\n"
            + context_block
            + "\n\n"
            + "Use this context only as guidance. Do not fabricate medical facts."
        )
        history_messages = await self.build_llm_messages(
            db,
            conversation_id=conversation_id,
            user_id=user["id"],
            latest_user_prompt=user_prompt,
        )

        provider = get_llm_provider()
        request = ChatCompletionRequest(
            system_prompt=system_prompt,
            messages=history_messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        async for chunk in provider.stream_chat(request):
            if chunk.text:
                yield chunk.text
            if chunk.done:
                break

    @staticmethod
    def _build_context_block(user: dict[str, Any], prediction_summary: str | None) -> str:
        personal = user.get("personal_info") or {}
        clinical = user.get("clinical_info") or {}
        medical = user.get("medical_info") or {}

        lines = [
            f"Full name: {personal.get('full_name')}",
            f"Primary concerns: {clinical.get('primary_concerns')}",
            f"Symptom onset age: {clinical.get('symptom_onset_age')}",
            f"Current medications: {medical.get('current_medications')}",
            f"Sleep patterns: {medical.get('sleep_patterns')}",
        ]

        if prediction_summary:
            lines.append(f"Latest prediction summary: {prediction_summary}")

        cleaned = [line for line in lines if line.split(": ", maxsplit=1)[-1] not in {"None", "", "null"}]
        return "\n".join(cleaned)[:4000]

    @staticmethod
    def _serialize_conversation(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "user_id": document["user_id"],
            "title": document.get("title"),
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }

    @staticmethod
    def _serialize_message(document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "conversation_id": document["conversation_id"],
            "user_id": document["user_id"],
            "role": document["role"],
            "content": document["content"],
            "provider": document.get("provider"),
            "model_name": document.get("model_name"),
            "created_at": document["created_at"],
        }
