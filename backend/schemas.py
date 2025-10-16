from sqlmodel import SQLModel
from datetime import datetime
from typing import List, Optional


# Message Schemas
class MessageCreate(SQLModel):
    content: str


class MessagePublic(SQLModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime


# Conversation Schemas
class ConversationCreate(SQLModel):
    title: Optional[str] = None


class ConversationPublic(SQLModel):
    id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessagePublic] = []
