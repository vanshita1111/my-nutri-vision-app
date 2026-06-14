"""
Pydantic schemas for the AI Nutrition Buddy feature.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None   # None = start new conversation
    stream: bool = True


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageOut
