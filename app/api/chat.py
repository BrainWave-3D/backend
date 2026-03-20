from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.metrics import (
    CHAT_ACTIVE_CONNECTIONS,
    CHAT_MESSAGES_TOTAL,
    CHAT_RESPONSE_DURATION,
    LLM_PROVIDER_ERRORS,
)
from app.core.security import _ensure_token_not_blacklisted, decode_token, get_current_user
from app.db.session import get_database
from app.schemas.chat import (
    ChatConversationCreateResponse,
    ChatConversationListResponse,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatSendResponse,
    ChatWSIncoming,
)
from app.services.chat_service import ChatService
from app.services.user_service import UserService

router = APIRouter(prefix="/chat", tags=["chat"])
_chat_service = ChatService()
_user_service = UserService()


@router.post("/conversations", response_model=ChatConversationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatConversationCreateResponse:
    conversation = await _chat_service.create_conversation(db, user_id=current_user["id"])
    return ChatConversationCreateResponse(conversation=conversation)


@router.get("/conversations", response_model=ChatConversationListResponse)
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatConversationListResponse:
    items = await _chat_service.list_conversations(db, user_id=current_user["id"], limit=limit, skip=skip)
    return ChatConversationListResponse(items=items)


@router.get("/conversations/{conversation_id}/messages", response_model=ChatMessageListResponse)
async def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatMessageListResponse:
    conversation = await _chat_service.get_conversation(db, conversation_id=conversation_id, user_id=current_user["id"])
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    items = await _chat_service.list_messages(
        db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
        limit=limit,
        skip=skip,
    )
    return ChatMessageListResponse(items=items)


@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
async def send_message(
    conversation_id: str,
    payload: ChatMessageCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatSendResponse:
    start = datetime.now().timestamp()
    provider = settings.llm_provider
    conversation = await _chat_service.get_conversation(db, conversation_id=conversation_id, user_id=current_user["id"])
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    user_message = await _chat_service.save_message(
        db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
        role="user",
        content=payload.content,
    )
    CHAT_MESSAGES_TOTAL.labels(channel="http", role="user", status="ok", provider=provider).inc()

    chunks: list[str] = []
    try:
        async for text in _chat_service.stream_assistant_reply(
            db,
            conversation_id=conversation_id,
            user=current_user,
            user_prompt=payload.content,
            prediction_summary=payload.prediction_summary,
        ):
            chunks.append(text)
    except Exception:
        CHAT_MESSAGES_TOTAL.labels(channel="http", role="assistant", status="error", provider=provider).inc()
        LLM_PROVIDER_ERRORS.labels(provider=provider).inc()
        raise

    assistant_text = "".join(chunks).strip() or "I could not generate a response."
    assistant_message = await _chat_service.save_message(
        db,
        conversation_id=conversation_id,
        user_id=current_user["id"],
        role="assistant",
        content=assistant_text,
        provider=provider,
        model_name=settings.llm_model_name,
    )
    CHAT_MESSAGES_TOTAL.labels(channel="http", role="assistant", status="ok", provider=provider).inc()
    CHAT_RESPONSE_DURATION.labels(channel="http", provider=provider).observe(datetime.now().timestamp() - start)

    updated_conversation = await _chat_service.get_conversation(db, conversation_id=conversation_id, user_id=current_user["id"])
    if updated_conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return ChatSendResponse(
        conversation=updated_conversation,
        user_message=user_message,
        assistant_message=assistant_message,
    )


@router.post("/message", response_model=ChatSendResponse)
async def send_message_simple(
    payload: ChatMessageCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatSendResponse:
    conversation = await _chat_service.get_or_create_default_conversation(db, user_id=current_user["id"])
    return await send_message(
        conversation_id=conversation["id"],
        payload=payload,
        db=db,
        current_user=current_user,
    )


@router.get("/history", response_model=ChatMessageListResponse)
async def list_history_simple(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: dict = Depends(get_current_user),
) -> ChatMessageListResponse:
    conversation = await _chat_service.get_or_create_default_conversation(db, user_id=current_user["id"])
    items = await _chat_service.list_messages(
        db,
        conversation_id=conversation["id"],
        user_id=current_user["id"],
        limit=limit,
        skip=skip,
    )
    return ChatMessageListResponse(items=items)


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket, db: AsyncIOMotorDatabase = Depends(get_database)) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or "sub" not in payload or "jti" not in payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid access token")
            return
        await _ensure_token_not_blacklisted(db, payload["jti"])
        user = await _user_service.get_by_id(db, payload["sub"], include_password=False)
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User no longer exists")
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await websocket.accept()
    provider = settings.llm_provider
    CHAT_ACTIVE_CONNECTIONS.labels(provider=provider).inc()

    try:
        await websocket.send_json({"type": "ready", "provider": provider})
        while True:
            raw = await websocket.receive_json()
            incoming = ChatWSIncoming.model_validate(raw)

            conversation_id = incoming.conversation_id
            conversation = None
            if conversation_id:
                conversation = await _chat_service.get_conversation(db, conversation_id=conversation_id, user_id=user["id"])
                if conversation is None:
                    await websocket.send_json({"type": "error", "detail": "Conversation not found"})
                    continue
            else:
                conversation = await _chat_service.get_or_create_default_conversation(db, user_id=user["id"])
                conversation_id = conversation["id"]

            user_message = await _chat_service.save_message(
                db,
                conversation_id=conversation_id,
                user_id=user["id"],
                role="user",
                content=incoming.content,
            )
            CHAT_MESSAGES_TOTAL.labels(channel="websocket", role="user", status="ok", provider=provider).inc()

            await websocket.send_json(
                {
                    "type": "conversation",
                    "conversation_id": conversation_id,
                    "user_message_id": user_message["id"],
                }
            )

            started_at = datetime.now().timestamp()
            chunks: list[str] = []
            try:
                async for text in _chat_service.stream_assistant_reply(
                    db,
                    conversation_id=conversation_id,
                    user=user,
                    user_prompt=incoming.content,
                    prediction_summary=incoming.prediction_summary,
                ):
                    chunks.append(text)
                    await websocket.send_json({"type": "assistant_delta", "text": text})
            except Exception:
                CHAT_MESSAGES_TOTAL.labels(channel="websocket", role="assistant", status="error", provider=provider).inc()
                LLM_PROVIDER_ERRORS.labels(provider=provider).inc()
                await websocket.send_json({"type": "error", "detail": "Failed to generate response"})
                continue

            assistant_text = "".join(chunks).strip() or "I could not generate a response."
            assistant_message = await _chat_service.save_message(
                db,
                conversation_id=conversation_id,
                user_id=user["id"],
                role="assistant",
                content=assistant_text,
                provider=provider,
                model_name=settings.llm_model_name,
            )
            CHAT_MESSAGES_TOTAL.labels(channel="websocket", role="assistant", status="ok", provider=provider).inc()
            CHAT_RESPONSE_DURATION.labels(channel="websocket", provider=provider).observe(
                datetime.now().timestamp() - started_at
            )

            await websocket.send_json(
                {
                    "type": "assistant_done",
                    "message_id": assistant_message["id"],
                    "conversation_id": conversation_id,
                }
            )
    except WebSocketDisconnect:
        return
    finally:
        CHAT_ACTIVE_CONNECTIONS.labels(provider=provider).dec()
