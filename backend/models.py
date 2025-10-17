from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id")
    role: str  # 'user' or 'assistant'
    content: str
    reasoning: Optional[str] = None  # AI reasoning (if available)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    conversation: Optional["Conversation"] = Relationship(back_populates="messages")


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    messages: List["Message"] = Relationship(back_populates="conversation", cascade_delete=True)
