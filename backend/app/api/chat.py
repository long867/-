"""Authenticated consultation, session lifecycle and verified-answer SSE."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text

from app.api.deps import DB, CurrentUser
from app.core.observability import consultation
from app.models import ChatMessage, ChatSession
from app.rag.conversation_context import ConversationContext
from app.rag.localization import localized_history
from app.rag.qa_chain import answer_question
from app.schemas.api import ChatInput, ChatMessageOut, ChatOut, ChatSessionOut

router = APIRouter(tags=["consultation"])


async def owned_session(session_id: UUID, db: DB, user: CurrentUser) -> ChatSession:
    """Hide both absent and other users' sessions behind the same 404."""
    item = await db.get(ChatSession, session_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "会话不存在")
    return item


@router.post("", response_model=ChatOut)
async def chat(payload: ChatInput, db: DB, user: CurrentUser) -> ChatOut:
    """Return a persisted answer with sentence-level evidence citations."""
    async with consultation():
        result = await answer_question(db, user.id, payload)
        await db.commit()
    return result


@router.get("/sessions", response_model=list[ChatSessionOut])
async def sessions(db: DB, user: CurrentUser) -> list[ChatSession]:
    return list(
        (
            await db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user.id)
                .order_by(ChatSession.created_at.desc())
                .limit(50)
            )
        ).all()
    )


@router.get("/history/{session_id}", response_model=list[ChatMessageOut])
@router.get(
    "/sessions/{session_id}",
    response_model=list[ChatMessageOut],
    include_in_schema=False,
)
async def history(session_id: UUID, db: DB, user: CurrentUser) -> list[ChatMessageOut]:
    """Return the latest 200 turns in chronological order."""
    await owned_session(session_id, db, user)
    rows = list(
        (
            await db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(200)
            )
        ).all()
    )
    return await localized_history(db, rows[::-1])


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: UUID, db: DB, user: CurrentUser) -> Response:
    """Serialize deletion with active turns and cascade-delete owned messages."""
    await owned_session(session_id, db, user)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(session_id)}
    )
    item = await owned_session(session_id, db, user)
    await db.delete(item)
    await db.commit()
    return Response(status_code=204)


@router.get("/session/{session_id}/context", response_model=ConversationContext)
async def session_context(
    session_id: UUID, db: DB, user: CurrentUser
) -> ConversationContext:
    """Expose only the authenticated user's structured business context."""
    item = await owned_session(session_id, db, user)
    return ConversationContext.model_validate(item.context_json.get("memory", {}))


@router.delete("/session/{session_id}/context", response_model=ConversationContext)
async def clear_context(
    session_id: UUID, db: DB, user: CurrentUser
) -> ConversationContext:
    """Forget prior context and prompt history while keeping visible message records."""
    await owned_session(session_id, db, user)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(session_id)}
    )
    item = await db.get(ChatSession, session_id, populate_existing=True)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "会话不存在")
    empty = ConversationContext()
    item.context_json = {
        "memory": empty.model_dump(mode="json"),
        "cleared_at": datetime.now(UTC).isoformat(),
    }
    await db.commit()
    return empty


def sse(event: str, data: dict) -> str:
    """Encode frames as JSON so embedded newlines cannot inject SSE events."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def stream_chat(
    payload: ChatInput,
    request: Request,
    db: DB,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream progress and verified text; commit before publishing the done event.

    Model output is validated as a whole first. Text deltas then expose only
    verified answer content, never partially invented citation markers.
    """
    if payload.session_id:
        await owned_session(payload.session_id, db, user)
    user_id = user.id

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def status(phase: str) -> None:
            await queue.put(sse("status", {"phase": phase}))

        async def produce() -> ChatOut:
            async with consultation():
                result = await answer_question(db, user_id, payload, on_status=status)
                await db.commit()
            return result

        task = asyncio.create_task(produce())
        pending: asyncio.Task | None = None
        try:
            while not task.done():
                pending = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {pending, task}, timeout=15, return_when=asyncio.FIRST_COMPLETED
                )
                if pending in done:
                    yield pending.result()
                else:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                    if not task.done():
                        yield ": heartbeat\n\n"
                if await request.is_disconnected():
                    return
            while not queue.empty():
                yield queue.get_nowait()
            result = await task
            yield sse(
                "sources",
                {"sources": [item.model_dump(mode="json") for item in result.sources]},
            )
            for offset in range(0, len(result.answer), 48):
                yield sse("delta", {"text": result.answer[offset : offset + 48]})
                await asyncio.sleep(0)
            yield sse("done", result.model_dump(mode="json"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await db.rollback()
            structlog.get_logger().warning(
                "chat_stream_failed", error_type=type(exc).__name__
            )
            detail = (
                exc.detail if isinstance(exc, HTTPException) else "咨询服务暂时不可用"
            )
            yield sse("error", {"detail": detail})
        finally:
            if pending and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if db.in_transaction():
                await db.rollback()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
