"""
AI Nutrition Buddy — conversational nutrition assistant.

POST /buddy/chat            — send a message, stream the response via SSE
GET  /buddy/conversations   — list user's conversations
GET  /buddy/conversations/{id} — full conversation with messages
DELETE /buddy/conversations/{id} — delete a conversation
DELETE /buddy/conversations    — delete all conversations (GDPR)
"""

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.buddy import ChatRequest, ConversationSummary, ConversationDetail
from app.services.buddy_context import assemble_context

log = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT_BASE = """You are NutriBuddy, an expert AI nutrition assistant built into the NutriVision app.
You have deep knowledge of nutrition science, Indian cuisine (IFCT 2017 data), sports nutrition,
women's health, and practical meal planning.

Your personality:
- Warm, encouraging, and non-judgmental
- Specific and data-driven (cite numbers from the user's actual data)
- Concise: 2-4 short paragraphs max unless the user asks for detail
- Use plain language, not medical jargon
- When relevant, reference what the user actually ate today or this week
- If you don't have enough data to answer confidently, say so and ask a follow-up question

Formatting rules (strictly follow these):
- Use **bold** only for key numbers or food names — at most 2-3 times per response
- Use "- " bullet points when listing 3+ items, not long comma-separated prose
- Use numbered lists only for steps or ordered advice
- No headers (## or ###) for short replies — only for detailed breakdowns
- Never start every line with bold; bold mid-sentence for emphasis only
- Keep bullets short: one idea per bullet, no sub-bullets

Rules:
- NEVER diagnose medical conditions or replace professional medical advice
- For serious health issues, recommend consulting a doctor or registered dietitian
- If user asks about medications or supplements beyond basic vitamins, recommend professional consultation
- Do not provide weight-loss advice beyond standard nutrition guidance

The user's current nutritional context is below. Use it to give personalised, specific answers.
"""

RATE_LIMIT_FREE    = 30   # messages per day
RATE_LIMIT_PREMIUM = 200


# ── Rate limiting ─────────────────────────────────────────────────────────────

def _check_rate_limit(user: User) -> None:
    try:
        import redis as _r
        from datetime import date
        rc = _r.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"nv:buddy:rl:{user.id}:{date.today().isoformat()}"
        count = rc.incr(key)
        if count == 1:
            rc.expire(key, 86400)
        limit = RATE_LIMIT_PREMIUM if user.is_premium else RATE_LIMIT_FREE
        if count > limit:
            raise HTTPException(429, f"Daily message limit ({limit}) reached. Upgrade to premium for more.")
    except HTTPException:
        raise
    except Exception:
        pass   # Redis down — allow through


# ── Conversation helpers ──────────────────────────────────────────────────────

async def _get_or_create_conversation(
    conversation_id: str | None,
    user: User,
    first_message: str,
    db: AsyncSession,
) -> Conversation:
    if conversation_id:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv or conv.user_id != user.id:
            raise HTTPException(404, "Conversation not found.")
        return conv

    # Auto-title from the first user message (truncated)
    title = first_message[:60].strip() + ("…" if len(first_message) > 60 else "")
    conv  = Conversation(id=str(uuid.uuid4()), user_id=user.id, title=title)
    db.add(conv)
    await db.flush()
    return conv


async def _load_history(conversation_id: str, db: AsyncSession, limit: int = 20) -> list[dict]:
    """Return last N messages as Claude-format dicts."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    msgs = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs]


# ── Streaming generator ───────────────────────────────────────────────────────

_SYSTEM_BLOCK = lambda prompt: prompt  # plain string — cache_control requires ≥1024 tokens and a beta flag; skip it


async def _stream_claude(
    system_prompt: str,
    history: list[dict],
    user_message: str,
) -> AsyncGenerator[str, None]:
    """True real-time streaming using AsyncAnthropic — yields each token as it arrives."""
    import anthropic

    client   = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = history + [{"role": "user", "content": user_message}]

    async with client.messages.stream(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_BLOCK(system_prompt),
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield f"data: {json.dumps({'delta': text})}\n\n"

    yield "data: [DONE]\n\n"


async def _call_claude_async(
    system_prompt: str,
    history: list[dict],
    user_message: str,
) -> str:
    """Non-streaming path using AsyncAnthropic."""
    import anthropic

    client   = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = history + [{"role": "user", "content": user_message}]

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_BLOCK(system_prompt),
        messages=messages,
    )
    return response.content[0].text


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/buddy/chat")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to NutriBuddy.
    With stream=true (default) returns Server-Sent Events.
    With stream=false returns a JSON ChatResponse.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(503, "AI Buddy is not configured on this server.")

    _check_rate_limit(current_user)

    context_block  = await assemble_context(current_user, db)
    system_prompt  = SYSTEM_PROMPT_BASE + "\n\n" + context_block

    conv = await _get_or_create_conversation(
        body.conversation_id, current_user, body.message, db
    )
    history = await _load_history(conv.id, db)

    # Save user message now (before streaming so conv_id is available)
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()

    if body.stream:
        # Streaming SSE response — collect full text, save assistant message after
        async def event_stream() -> AsyncGenerator[str, None]:
            # Prepend conversation_id so the client knows which conv this belongs to
            yield f"data: {json.dumps({'conversation_id': conv.id})}\n\n"

            full_text = []
            try:
                async for chunk in _stream_claude(system_prompt, history, body.message):
                    if chunk == "data: [DONE]\n\n":
                        break
                    yield chunk
                    try:
                        payload = json.loads(chunk[6:])   # strip "data: "
                        full_text.append(payload.get("delta", ""))
                    except Exception:
                        pass
            except Exception as exc:
                log.error("NutriBuddy streaming error conv=%s: %s", conv.id, exc)
                yield f"data: {json.dumps({'error': 'Something went wrong — please try again.'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Persist assistant reply
            assistant_reply = "".join(full_text)
            if assistant_reply.strip():
                asst_msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    role="assistant",
                    content=assistant_reply,
                )
                db.add(asst_msg)
                await db.commit()

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming path
    reply_text = await _call_claude_async(system_prompt, history, body.message)
    asst_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        role="assistant",
        content=reply_text,
    )
    db.add(asst_msg)
    await db.commit()

    return {
        "conversation_id": conv.id,
        "message": {
            "id":         asst_msg.id,
            "role":       "assistant",
            "content":    reply_text,
            "created_at": asst_msg.created_at,
        },
    }


@router.get("/buddy/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    convs = result.scalars().all()
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages),
        )
        for c in convs
    ]


@router.get("/buddy/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found.")
    return conv


@router.delete("/buddy/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(404, "Conversation not found.")
    await db.delete(conv)
    await db.commit()


@router.delete("/buddy/conversations", status_code=204)
async def delete_all_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GDPR — erase all chat history for this user."""
    stmt = select(Conversation).where(Conversation.user_id == current_user.id)
    result = await db.execute(stmt)
    for conv in result.scalars().all():
        await db.delete(conv)
    await db.commit()
